# ポケモンFRLGスイッチ版相性チェッカー：英語名・発音追加（確定仕様）

> 本ファイルは `FRLG_PRONUNCIATION_FEATURE_SPEC_DRAFT.md` をベースに、現コードと
> 照らし合わせて精査・改訂した**確定仕様**である。素案ドラフトは削除して良い。
> 各フェーズ終了時に立ち止まり、しんごさんの確認後に次へ進む運用は維持。

---

## 1. 目的

奥さん（より）が FRLG プレイ中に、ポケモン名表示から **英語名** と **英語発音** を
学べるようにする。家族の英語学習補助を兼ねた拡張。

## 2. スコープ

既存 242 体（Kanto 1-151 + Gen2 161-251、ジョウト御三家系統 152-160 は除外）
に加え、以下 **FRLG 配信イベント Gen3 4 体** を追加。合計 **246 体**。

| ID | Pokemon | 入手経路 |
|---|---|---|
| 380 | Latias | エオンチケット → サザンアイランド |
| 381 | Latios | エオンチケット → サザンアイランド |
| 385 | Jirachi | コロシアム/Pokemon Channel ボーナス |
| 386 | Deoxys | オーロラチケット → バースアイランド |

Kyogre/Groudon/Rayquaza (382-384) は R/S/E 配布で FRLG 配信枠外のため除外。

## 3. 音源戦略：Web Speech API（ブラウザ内蔵 TTS）

- `window.speechSynthesis` + `SpeechSynthesisUtterance(name_en)` を使用
- 完全オフライン、外部 API なし、課金リスク・URL 空振りリスクともゼロ
- iPhone 内蔵の英語音声（Samantha 等）で発音
- 設定：`lang='en-US'`, `rate=0.85`（学習用にやや遅め）
- フィーチャー検出失敗時は 🔊 ボタン非表示（フォールバック）

外部リンク（Forvo / Bulbapedia）は採用しない。理由：奥さんは戦闘中の片手操作で
使う想定なので外部遷移はコストが高い、また音源欠落で空ページに飛ぶリスクを排除。

## 4. データスキーマ追加

既存 `pokemon` エントリに 1 フィールド追加（`name_en_katakana` は別ファイル管理、
ビルド時に `data.json` へマージ）。

```json
{
  "id": 6,
  "name_ja": "リザードン",
  "name_hira": "りざーどん",
  "name_en": "Charizard",
  "name_en_katakana": "チャリザード",
  "types": ["fire", "flying"],
  "abilities": ["blaze"]
}
```

- `name_en`：`build_data.py` が `species.names` から `language.name == "en"` を抽出
- `name_en_katakana`：別ファイル `katakana_readings.json` を手作業で用意し、ビルド時にマージ
- 既存フィールドは一切変更しない（後方互換 100%）

## 5. カタカナ読み方針：手作業表

自動生成は採用しない。固有名詞は規則で割らない（Charizard, Gyarados, Mewtwo …）し、
発音学習が目的なら誤った読みはノイズになる。

**運用：**

- リポジトリに `katakana_readings.json` を置く
  ```json
  {
    "Charizard": "チャリザード",
    "Pikachu": "ピカチュー",
    "Bulbasaur": "バルバソー"
  }
  ```
- 初稿は Claude が全 246 体分を Bulbapedia の発音記述等を参考に書く
- しんごさんが目視レビュー → 必要に応じ手で修正 → コミット
- `build_data.py` 実行時にマージ。未登録のキーは警告ログを出してスキップ
  （`name_en_katakana` フィールドを空文字で出力、フロントはフォールバック表示）

## 6. 表示レイアウト（Option G）

iPhone 390px 幅で 2 行構成。英語行はやや小さく・グレーで補助情報として置く。

```
┌────────────────────────────┐
│ #006                       │
│ リザードン                  │ ← H2, 主役
│ Charizard (チャリザード) 🔊 │ ← 小さい字, グレー
│ [FUOCO] [VOLANTE]          │
│ 特性: もうか               │
└────────────────────────────┘
```

- 英語行 CSS：`font-size: 0.85em`, `color: #6b7280` 程度
- 🔊 ボタン：見た目は小さくてもタップ領域 **min 44×44px**（透明 padding で確保）
- 英語フォントは system-ui の英字部分でOK
- 英語名が未取得（PokeAPI に無いなど）の場合は英語行ごと出さずフォールバック

## 7. キャッシュ整合性

既存仕組みで足りる。新規対応は不要：

- `data.json` は SW で **network-first**（`docs/service-worker.js:62-79`）→ デプロイ直後に最新が反映
- 静的シェル（HTML/JS/CSS）は `CACHE_VERSION` を `build_data.py` が自動バンプ（`build_data.py:404-440`）

**フェーズ5 では「ビルド後 PWA リロード1回で英語名と 🔊 が見える」ことの動作確認のみ。**

## 8. 実装フェーズ

各フェーズ終了時に **立ち止まって報告**、しんごさんの確認後に次へ進む。

### フェーズ1：`build_data.py` 拡張＋データ再生成

- `pokemon_ids` に `[380, 381, 385, 386]` を追加
- `english_name(species)` ヘルパー追加
- pokemon エントリに `name_en` を付与
- データ再生成して 246 件出ること、4 体の英語名が正しいこと
- 既存 242 件の `name_ja` / `types` / `abilities` が一切変わっていないこと（diff で確認）
- **報告 → 確認待ち**

### フェーズ2：`katakana_readings.json` 初稿作成

- Claude が 246 体分のカタカナ読みを作成
- レビュー支援として `katakana_review.md`（英名・カタカナ・備考 の表）も併せて出力
- **しんごさんレビュー → 修正 → 確定**

### フェーズ3：カタカナを `data.json` にマージ

- `build_data.py` が `katakana_readings.json` を読み、`name_en_katakana` を付与
- 未登録キーは警告ログを出して空文字で出力
- 再生成して全 246 体に `name_en_katakana` が入ること
- **報告 → 確認待ち**

### フェーズ4：フロント表示更新

- `docs/index.html`：result-head に英語行のスケルトン追加
- `docs/app.js`：`renderResult()` に英語名描画と `speechSynthesis` 連携を追加
- `docs/style.css`：英語行スタイル、🔊 ボタンのタップ領域確保
- ローカルで `python3 -m http.server` 等で開き、複数ポケモンで表示と発音を確認
- **報告 → 確認後にコミット**

### フェーズ5：PWA 動作確認

- iPhone Safari でリロード、新表示が出ること
- 機内モードで再アクセスし、表示・発音ともオフラインで動くこと
- 問題なければ push

## 9. 全体ルール（運用）

- 推測で進めない。不明点があったら質問する
- 各フェーズで進捗報告し、勝手に次へ進まない
- バックアップなしの破壊的変更禁止
- コミットはしんごさん確認後、小さく刻む
- カタカナ読みは Claude 初稿 → しんごさん目視レビュー前提
