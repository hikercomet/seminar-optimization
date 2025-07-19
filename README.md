以下は、**初心者にもわかりやすくまとめ直した配布用説明文**デス。
これをよめば導入がくそほど簡単にできまふ！
わかんなかったらすぐしたで聞いてくだサイ。
機械苦手なNさんもできたので多分ほとんどの人できる

## 😎 **困ったときは**
「こここうした方がいい！」や「動かない！」などあれば
**ここにコメントしてくれたら対応します！**
（BY Nしお）
---


## 🔧 **使い方（まとめ）**

### 1️⃣ プログラムをダウンロードする

方法は2つあります。どちらでもOK！

#### ■ 【簡単】ZIPファイルでダウンロード
1. こちらをクリック
   👉 [https://github.com/hikercomet/seminar-optimization](https://github.com/hikercomet/seminar-optimization)
2. 右上の「**Code**」ボタンをクリック
3. 「**Download ZIP**」を選ぶ
4. ダウンロードしたZIPを**解凍して使う**

---

#### ■ 【慣れてる人向け】Gitでクローンする
以下のコマンドを実行します（Gitが使える人用）

```bash
git clone https://github.com/hikercomet/seminar-optimization.git
```



### 2️⃣ プログラムを動かす
解凍（またはクローン）したフォルダを開き、
中のファイル（例：`main.py`など）を動かせばOK！

**VS Codeで開きたい人**は
→ VS Codeから「フォルダを開く」でそのまま開けます。

---

### 3️⃣ 最新版に更新したいとき
Gitが使える人は以下を実行すると、最新版が取れます。

```bash
git pull origin main
```
---

## ⚠️ **注意（これテストに出まふ！！）**

* **勝手に編集して直接pushするとエラーになります！**
  （もし編集したい場合は事前に連絡してください）

* **作業前は `git pull` をして最新版にしておくと安心デス。**

---

## 📝 **作業の流れ（復習）**

| 何をしたい？   | やること                      　　  |
| ------------- | ---------------------------------- |
| とりあえず使う | ZIPをダウンロード（または`git clone`）|
| 最新版を取りたい| `git pull origin main`             |       
| 編集したい     | Forkして自分のコピーを作る           |

---
## 7. まとめ（作業の流れ、これテストに出ます）

1. 最初だけ git clone URL でリポジトリをコピー
2. 作業を始める前に git pull origin main
3. ファイルを編集
4. git add . で変更を登録
5. git commit -m "説明" で変更を保存
6. git push origin main で共有
7. また2に戻って繰り返し！

## 🔗 **リポジトリURL**
(https://github.com/hikercomet/seminar-optimization)
ちな、私のユーザー名はhikercometとなっております。
---


# 【VS Code Live Shareの使い方】
もし「一緒にリアルタイムでコード見たい・動かしたい！」となったら
**Live Share**という機能を使います。

---

## 💻 **準備するもの**

1. **VS Code（無料）**
   → [https://code.visualstudio.com/](https://code.visualstudio.com/)

2. 拡張機能「Live Share」を入れる
   → VS Codeの左側「拡張機能」から「Live Share」と検索してインストール。

---

## 🚪 **参加する方法**

1. **送られてきたリンクをクリック**（`vsls://` または `https://`形式）
2. **VS Codeで開く** → 自動でLive Shareに参加できます！

---

## 👀 **できること**

* **同じファイルをリアルタイムで見れる・編集できる**
* **一緒にコード実行・ターミナル共有できる**
* **Webアプリも共有可能（サーバー共有）**
* **ブレークポイント共有・デバッグ可能**
* **カーソル位置を同期して解説できる**

---

## ⏳ **リンクの有効期限は？**

* **一度閉じたらリンクは無効になります。**
  （その都度、新しいリンクを発行します）

---

## 🗣️ **よくある質問**

| 質問                   | 回答                            |
| ---------------------- | ------------------------------ |
| 見るだけ？              | 編集もできます（ホストの設定次第）|
| Web版VS Codeでもできる？ | 基本はPC版VS Code推奨           |



---

## 📺 **参考リンク**

* 公式解説（英語）
  [https://aka.ms/vsls-docs](https://aka.ms/vsls-docs)

* 使い方動画（日本語）
  [https://www.youtube.com/watch?v=ArX6E7fhhOk](https://www.youtube.com/watch?v=ArX6E7fhhOk)

Sisitem Structure
seminar_optimization/
│
├─ main.py
├─ optimizer.py
├─ output.py
├─ evaluation.py
├─ models.py
└─ utils.py