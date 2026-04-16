# 案件収集ボット セットアップ手順

## 全体の流れ
1. Gmailアプリパスワードを取得（発行済みならスキップ）
2. GitHubにリポジトリを作成・ファイルをアップロード
3. GitHub Secrets に Gmail 認証情報を登録
4. GitHub Pages を有効化（ダッシュボード公開）
5. index.html にGitHubユーザー名を設定
6. 動作確認

---

## STEP 1: Gmailのアプリパスワードを取得（発行済みならスキップ）

1. https://myaccount.google.com/security を開く
2. 「2段階認証プロセス」が**オン**になっているか確認
3. 検索バーに「アプリパスワード」と入力して開く
4. アプリ名に「案件通知」と入力 → 「作成」
5. **表示された16桁のパスワードを保管**（二度と表示されない）

---

## STEP 2: GitHubにリポジトリを作成

1. https://github.com を開いてログイン
2. 「New repository」をクリック
3. 設定:
   - Repository name: `job-search-bot`
   - **Public**（GitHub Pages を無料で使うために必要）
   - 「Create repository」をクリック
4. このフォルダ内の全ファイルをアップロード:
   ```bash
   cd /Users/takahashishunichi/Desktop/ポートフォリオ/Claude/job-search-bot
   git init
   git add .
   git commit -m "初期設定"
   git remote add origin https://github.com/あなたのユーザー名/job-search-bot.git
   git branch -M main
   git push -u origin main
   ```

---

## STEP 3: GitHub Secrets に Gmail 認証情報を登録

1. GitHubのリポジトリページ →「Settings」→「Secrets and variables」→「Actions」
2. 「New repository secret」を3回クリックして以下を登録:

| Name | 値 |
|------|----|
| `GMAIL_FROM` | 送信元Gmailアドレス（例: yourname@gmail.com） |
| `GMAIL_TO` | 通知受信アドレス（同じGmailでもOK） |
| `GMAIL_APP_PW` | STEP1の16桁アプリパスワード |

---

## STEP 4: GitHub Pages を有効化（ダッシュボード公開）

1. リポジトリの「Settings」→ 左メニュー「Pages」
2. Source: **Deploy from a branch**
3. Branch: `main` / Folder: `/docs`
4. 「Save」をクリック
5. 数分後に `https://あなたのユーザー名.github.io/job-search-bot/` が公開される

**このURLをスマホのホーム画面に追加すれば、アプリ感覚で使えます。**

---

## STEP 5: ダッシュボードにGitHubユーザー名を設定

`docs/index.html` の以下の行を編集:

```javascript
const GITHUB_USER = "tksami22";  // 設定済み
```

変更後、再度 git push してください。

---

## STEP 6: 動作確認（手動実行）

1. GitHubのリポジトリページ →「Actions」タブ
2. 左側の「案件収集」をクリック
3. 「Run workflow」→「Run workflow」をクリック
4. 約2〜3分後:
   - Gmailに案件通知メールが届く
   - ダッシュボードを開くと案件が表示される

---

## スマホから手動実行する2つの方法

### 方法A: ダッシュボードの「▶ 今すぐ更新」ボタン
→ GitHubのActions画面が開くので「Run workflow」をタップ

### 方法B: GitHubアプリから
1. GitHub公式アプリをインストール
2. リポジトリ →「Actions」→「案件収集」→「Run workflow」

---

## 自動実行スケジュール

現在の設定: **平日 朝9時・夜18時** に自動実行

変更する場合は `.github/workflows/search_jobs.yml` の cron 行を編集:
```yaml
- cron: '0 0 * * 1-5'   # JST 9:00（UTC 0:00）
- cron: '0 9 * * 1-5'   # JST 18:00（UTC 9:00）
```

スケジュール不要（手動のみ）にする場合は `schedule:` ブロックを削除。

---

## 検索キーワードのカスタマイズ

`search_jobs.py` の `KEYWORDS` リストを編集してください。
