---
title: 通知メールの重複送信をどう防ぐか
no: 10
genre: 信頼性設計
date: 2026-09-13
xPostedAt: null
tags: [冪等性, メッセージング, DB]
ads: true
description: リトライで同じ通知メールが 2 通届く問題を題材に、送信ジョブの冪等性をどこで担保するかを設計ケーススタディとして整理する。
---
# 設計ケーススタディ 10: 通知メールの重複送信をどう防ぐか

## Problem

注文確定時に「ご注文ありがとうございます」メールを送るバッチがある。
構成は次のとおりで、送信 API のタイムアウト時にジョブが自動リトライされる。

```text
+----------+     +-----------+     +------------+     +-----------+
|  Orders  | --> | Job Queue | --> | Mail Worker| --> | Mail API  |
|  (DB)    |     | (Redis)   |     | (Python)   |     | (SaaS)    |
+----------+     +-----------+     +------------+     +-----------+
                                         |  timeout -> retry
                                         +------------------+
                                                            |
                                              same job runs again
```

障害時に Mail API が「受け付けたが応答を返す前に切断」すると、
リトライで **同じ注文に対して 2 通目** が送られる。実際に月に数件、顧客から指摘があった。

制約:

- Mail API 側に重複排除の仕組みは無い（Idempotency-Key 非対応）
- Worker は複数プロセスで並列実行される
- 注文テーブルに列を追加するのは可能だが、送信履歴の専用テーブルは無かった

## Question

「送信したかどうか」を **どこで・どの粒度で** 記録すれば、並列リトライがあっても 1 注文 1 通に収まるか。

## 自分の回答

`orders` テーブルに `mail_sent_at` 列を足し、送信前にフラグを立ててから送る案にした。

```sql
-- 送信前にフラグを立てる（先に立てた者だけが送る）
UPDATE orders
   SET mail_sent_at = NOW()
 WHERE id = :order_id
   AND mail_sent_at IS NULL;
-- 更新行数が 1 のときだけ送信処理へ進む
```

```python
def send_order_mail(order_id: int) -> None:
    rows = db.execute(
        "UPDATE orders SET mail_sent_at = NOW() "
        "WHERE id = %s AND mail_sent_at IS NULL",
        (order_id,),
    ).rowcount
    if rows == 0:
        return  # 既に誰かが送っている（or 送信中）
    mail_api.send(order_id)
```

## なぜそう考えたか

- `UPDATE ... WHERE mail_sent_at IS NULL` は 1 行に対する原子的な CAS なので、
  並列に走っても更新できるのは 1 プロセスだけになる
- テーブル追加なしで済み、変更範囲が最小
- 「送信済みかどうか」は注文の属性として自然に読める

却下した案:

| 案 | 却下理由 |
|---|---|
| Redis の `SETNX` でロック | Redis 障害時に判定が消える。DB と二重管理になる |
| Mail API 側で重複排除 | 非対応。乗り換えは別プロジェクト |
| リトライを止める | 本当のネットワーク障害で未送信のまま残る |

## AIレビュー

AI に上の案をレビューさせたところ、主に次の 3 点の指摘があった。

> 1. フラグを「送信前」に立てると、送信に失敗した場合にフラグだけ残って **永久に未送信** になる。
>    `mail_sent_at` は「送信完了」ではなく「送信を試みた」の意味になっている。
> 2. Mail API のタイムアウト（受理されたか不明）と、明確な失敗（4xx）を区別していない。
>    前者は再送してはいけないが、後者は再送してよい。
> 3. `orders` に列を足すと、将来「再送」や「別種の通知」を扱うときに列が増殖する。
>    通知の送信履歴は注文とは別のライフサイクルを持つ。

## 再考・気づき

指摘 1 が決定的だった。自分の案は「重複」は防ぐが「欠落」を生む。
状態を 3 つ（未送信 / 送信中 / 送信済み）に分け、送信履歴を別テーブルにした。

```text
            claim (INSERT ... ON CONFLICT DO NOTHING)
  [none] ---------------------------------------------> [sending]
                                                           |
                       +-----------------------------------+
                       |                                   |
                  API 2xx / timeout                    API 4xx
                       |                                   |
                       v                                   v
                   [sent]                              [failed]
                                                           |
                                          retry (UPDATE failed -> sending)
```

```sql
CREATE TABLE order_mail_log (
    order_id    BIGINT PRIMARY KEY REFERENCES orders(id),
    state       TEXT NOT NULL CHECK (state IN ('sending', 'sent', 'failed')),
    attempts    INT  NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

```python
def send_order_mail(order_id: int) -> None:
    # 1. claim: PRIMARY KEY 衝突で「誰かが先に取った」ことが分かる
    claimed = db.execute(
        "INSERT INTO order_mail_log (order_id, state, attempts) "
        "VALUES (%s, 'sending', 1) ON CONFLICT (order_id) DO NOTHING",
        (order_id,),
    ).rowcount == 1
    if not claimed:
        # failed のものだけ再挑戦できる
        claimed = db.execute(
            "UPDATE order_mail_log SET state='sending', attempts=attempts+1, updated_at=NOW() "
            "WHERE order_id=%s AND state='failed'",
            (order_id,),
        ).rowcount == 1
    if not claimed:
        return  # sending / sent は触らない

    # 2. send
    try:
        mail_api.send(order_id)
    except MailApiClientError:          # 4xx: 受理されていないので再送可
        db.execute("UPDATE order_mail_log SET state='failed' WHERE order_id=%s", (order_id,))
        raise
    except MailApiTimeout:              # 受理されたか不明: 再送しない側に倒す
        db.execute("UPDATE order_mail_log SET state='sent' WHERE order_id=%s", (order_id,))
        return
    db.execute("UPDATE order_mail_log SET state='sent' WHERE order_id=%s", (order_id,))
```

タイムアウトを `sent` に倒すのは「1 通も届かない」より「まれに 2 通届く」方がまだ良い、
という業務判断ではなく、その逆——今回は **顧客からの指摘が重複側** だったので欠落側に倒した。
ここは業務ごとに決める値であって、コードで決まる値ではない。

## 設計ポイント

- 冪等性は「送ったか」ではなく **「送ろうとしたか / 送れたか / 失敗したか」の状態遷移** として持つ
- claim は `INSERT ... ON CONFLICT` か `UPDATE ... WHERE state = ...` のような **DB の原子操作 1 つ** に寄せる
- 「不明（timeout）」をどちらに倒すかは業務要件。コードには判断ではなく設定として現れるべき
- 通知履歴のように独立したライフサイクルを持つものは、元エンティティに列を足さず別テーブルにする

## 実務ではどうだったか

`order_mail_log` 方式に切り替えて 2 か月、重複送信の報告はゼロ。
`failed` の再送は運用が手動で叩く SQL にしてあり、自動リトライは `sending` / `sent` を触らない。
`attempts` 列は今のところ監視のダッシュボードにしか使っていない。
