# Vue3 + Django REST Framework によるガントチャートシステム

vis-timeline（vis.js）を用いたガントチャート画面を、**ページング対応 API**・**双方向無限スクロール**・**ユーザー単位キャッシュ**・**ログイン必須**の要件に沿って実装したフルスタックのサンプルです。

- バックエンド: Django 5.2 + Django REST Framework（SQLite, セッション認証）
- フロントエンド: Vue 3 + Vite + axios + Pinia + Vuetify 3 + vis-timeline

---

## 1. 全体構成

```
gantt_app/
├── backend/                     # Django + DRF
│   ├── config/
│   │   ├── settings.py          # DRF/認証/ページング/キャッシュ/CORS 設定
│   │   └── urls.py              # API ルーティング
│   ├── gantt/
│   │   ├── models.py            # Group / Item（owner で所有者を分離）
│   │   ├── serializers.py       # vis.js 形式へのシリアライズ
│   │   ├── pagination.py        # ページサイズ 50 のページング
│   │   ├── datasource.py        # 外部取得を想定した 5 秒遅延データソース
│   │   ├── views.py             # ページング API + ユーザー単位キャッシュ
│   │   ├── auth_views.py        # CSRF / login / logout / me
│   │   └── management/commands/seed_demo.py  # デモデータ投入
│   └── db.sqlite3
└── frontend/                    # Vue 3 + Vite
    └── src/
        ├── api/
        │   ├── http.js          # axios インスタンス（CSRF/withCredentials）
        │   └── gantt.js         # API ラッパー
        ├── composables/
        │   ├── useQuery.js          # ★ TanStack Query 風のバニラ実装
        │   └── usePaginatedData.js  # ★ 双方向無限スクロールの蓄積ロジック
        ├── stores/auth.js       # Pinia 認証ストア
        ├── components/
        │   ├── GanttChart.vue   # ★ 子: vis-timeline 表示＋端検知（API は呼ばない）
        │   ├── GanttView.vue    # ★ 親: API 実行・ページ取得を担う
        │   └── LoginForm.vue
        └── App.vue              # 認証ゲート + レイアウト
```

---

## 2. 起動手順

### バックエンド（ポート 8000）

```bash
cd backend
# 依存: Django==5.2, djangorestframework, django-cors-headers
python3 manage.py migrate
python3 manage.py seed_demo            # デモユーザー(demo) と 300 groups / 1500 items を投入
python3 manage.py runserver 0.0.0.0:8000
```

デモログイン情報: ユーザー名 `demo` / パスワード `pass12345`

### フロントエンド（ポート 5173）

```bash
cd frontend
pnpm install
pnpm dev                                # http://localhost:5173
```

`vite.config.js` で `/api` を `http://localhost:8000` にプロキシしているため、CORS/Cookie もそのまま動作します。

---

## 3. API 仕様（すべてログイン必須）

| メソッド | パス | 説明 |
| --- | --- | --- |
| GET  | `/api/auth/csrf/`   | CSRF トークン取得 |
| POST | `/api/auth/login/`  | ログイン（username/password） |
| POST | `/api/auth/logout/` | ログアウト |
| GET  | `/api/auth/me/`     | 現在のユーザー |
| GET  | `/api/gantt/groups/?page=N` | groups を 50 件ずつ |
| GET  | `/api/gantt/items/?page=N`  | items を 50 件ずつ |
| GET  | `/api/gantt/page/?page=N`   | **無限スクロール用**: groups 50 件＋その範囲の items を同梱 |
| POST | `/api/gantt/cache/clear/`   | 自分のキャッシュのみ破棄（動作確認用） |

`/api/gantt/page/` のレスポンス例:

```json
{
  "count": 300, "total_pages": 6, "current_page": 1, "page_size": 50,
  "has_next": true, "has_previous": false,
  "groups": [ { "id": 1, "content": "リソース 001", "order": 1 }, ... ],
  "items":  [ { "id": 11, "group": 1, "content": "タスク 1-1", "start": "...", "end": "..." }, ... ]
}
```

---

## 4. 要件への対応

| 要件 | 対応内容 |
| --- | --- |
| vis.js でガントチャート（groups/items 必須） | `GanttChart.vue` が `vis-timeline` を用い、`groups`/`items` を **必須 props** として受け取り描画 |
| API はページング対応・ページサイズ 50 | DRF の `PAGE_SIZE = 50`、および `/gantt/page/` で groups 50 件単位にスライス |
| 大量データのレンダリング対策 | **グループ連動ページング**で 1 ページ分（groups 50＋該当 items）だけ描画。無限スクロールで必要分のみ取得 |
| 上下スクロール対応 | `vis-timeline` の `verticalScroll` を有効化し、縦スクロールパネルを監視 |
| 端到達で再読み込み・既存データ保持・違和感なく連結 | `usePaginatedData` が取得済み groups/items を保持し、末尾/先頭に **id 重複除去しつつ連結**。上方向追加時はスクロール位置を補正 |
| axios / Pinia / Vuetify3 | HTTP は axios、認証状態は Pinia、UI は Vuetify3 |
| ガント用コンポーネント分離・API は親から実行 | 子 `GanttChart.vue` は表示と端検知のみ（`reach-top`/`reach-bottom` を emit）。親 `GanttView.vue` が API を実行 |
| useQuery をバニラ実装 | `composables/useQuery.js`（キャッシュ・重複抑止・staleTime・refetch を自前実装、外部ライブラリ非依存） |
| 外部取得想定で初回 5 秒 → 2 回目以降は高速 | `datasource.py` が 5 秒遅延を模擬し、`views.py` がキャッシュで 2 回目以降を即時化 |
| ログイン必須・全ユーザーに見えない | `IsAuthenticated` + `owner=request.user` で絞り込み。**キャッシュキーに `user.pk` を含め**ユーザー単位に分離 |

---

## 5. 設計のポイント

### 5.1 グループ連動ページング（レンダリング負荷対策）

groups を全件描画すると vis-timeline の描画コストが高くなります。本実装では `/gantt/page/` が **「groups を 50 件返すと同時に、その 50 グループに属する items だけ」** を返します。これにより、

- 画面に出ている行とそのバーが常に一致する
- 1 ページ分だけ描画すればよく、初期表示・スクロール時とも軽量

### 5.2 双方向無限スクロール（`usePaginatedData`）

- 最下部到達 → `loadNext()` が次ページを取得し **末尾に連結**
- 最上部到達 → `loadPrev()` が前ページを取得し **先頭に連結**し、追加した groups 件数を返す
- `GanttChart.vue` 側で `captureScroll()` → データ追加 → `restoreScroll()` を行い、**上方向追加時に表示位置がジャンプしない**よう scrollTop を補正
- `id` で重複除去するため、同じページを二重に取得しても表示は崩れない

### 5.3 useQuery（バニラ実装）

`useQuery.js` はモジュールスコープの `Map` をキャッシュとして、`data/error/isLoading/isFetching` などの状態、同一キーの重複リクエスト抑止、`staleTime`/`cacheTime`、`refetch` を提供します。親 `GanttView.vue` はページごとに `useQuery` を生成して取得するため、一度見たページの再取得はフロント側でも即時です。

### 5.4 ユーザー単位キャッシュ（情報分離）

`views.py` のキャッシュキーは `gantt:{kind}:user:{user.pk}` 形式です。`user.pk` を必ず含めることで、**あるユーザーのキャッシュが別ユーザーに参照されることはありません**。データ自体も `owner=request.user` で常に絞り込みます。

---

## 6. 動作検証の結果

- 未認証アクセス: `403`（拒否）
- `demo`: 1 回目 約 10 秒（groups+items の 5 秒×2）→ 2 回目 0.05 秒（自分のキャッシュにヒット）
- `alice`: `demo` のキャッシュは共有されず初回も約 10 秒 → 2 回目 0.05 秒（**ユーザー単位で完全分離**）
- 下方向スクロール: ページ 1→6 まで自動取得し、items 1500 件まで末尾連結
- 上方向スクロール: 開始ページ 3 から上スクロールで前ページが先頭挿入され、**表示中の行（リソース 101）が動かないまま**データが増える

> 補足: `GanttView.vue` には検証用に `?start=N` で開始ページを指定する分岐があります（既定は 1）。本番では削除して構いません。
