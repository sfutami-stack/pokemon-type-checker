# ポケモンタイプ相性早見ツール (FRLG専用)

Switch版『ポケットモンスター ファイアレッド・リーフグリーン』(GBA忠実移植)用の、
個人利用ポケモン名 → タイプ相性早見PWA。

- 対象: カントー151匹 + ナナシマで野生出現する第2世代ポケモン
- 仕様: 第3世代当時のタイプ相性表・特性に準拠 (フェアリーなし、Steel が Ghost/Dark を半減)
- 配布: 完成後にGitHub Pagesで公開し、iPhone/Androidの「ホーム画面に追加」でPWAとして利用

## ディレクトリ構成
```
.
├── README.md
├── build_data.py        # PokéAPIからdata.jsonを再生成するスクリプト
├── requirements.txt
├── .gitignore
└── docs/                # GitHub Pages公開対象
    ├── data.json        # build_data.pyで生成
    ├── index.html       # (Phase 2で作成)
    ├── app.js           # (Phase 2で作成)
    ├── style.css        # (Phase 2で作成)
    ├── manifest.json    # (Phase 3で作成)
    ├── service-worker.js# (Phase 3で作成)
    └── icons/           # (Phase 3で配置)
```

## ローカル実行 (Phase 2 以降)
docsの中身を静的サーバで配信するだけ。

```bash
python3 -m http.server 8000 -d docs
# ブラウザで http://localhost:8000/ を開く
```

## データ再ビルド (build_data.py)

PokéAPI v2 から各ポケモン・特性データを取得し、`docs/data.json` を再生成する。
初回は ~200 のHTTPリクエストが発生 (約2〜5分)。レスポンスは `.cache/` にキャッシュされる
ため、再実行は数秒で終わる。

```bash
# 初回 (venv作成 + 依存インストール)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# ビルド
.venv/bin/python3 build_data.py
```

データを完全に作り直したい場合はキャッシュを消す:
```bash
rm -rf .cache && .venv/bin/python3 build_data.py
```

## データ仕様メモ

### 対象ポケモンの選定ロジック
- ID 1〜151 (カントー全種): 全て収録
- ID 161〜251 (ジョウト全種、御三家系9匹を除く): 全て収録
  - 野生出現・カントーからの進化(クロバット/キレイハナ等)・通信進化(ハガネール/ハッサム等)・
    イーブイ分岐(エーフィ/ブラッキー)・ベイビィタマゴ(ピチュー等)・伝説の獣を全て含む
  - **除外**: ジョウト御三家系 (チコリータ・ヒノアラシ・ワニノコの9匹)。FRLG単体では入手不可
- 合計242匹

### 第3世代タイプの復元 (フェアリー対策)
PokéAPIの `types` フィールドも現在 (Gen 9) 状態を返すため、Gen 6でフェアリーに変更された
ポケモン (ピッピ・プリン・バリヤード・ピィ・トゲピー・トゲチック・ブルー・グランブル) は
そのままだとフェアリータイプになってしまう。`past_types` を参照してGen 3当時のタイプ
(ノーマル等) に復元している。

### 特性の Gen 3 化
PokéAPIの `abilities` フィールドは現在 (Gen 9) の特性配置を反映するため、`past_abilities` の
スロット単位差分を重ね合わせてGen 3時点の状態に戻している:
- ゲンガー: 現行=のろわれボディ → 修正後=ふゆう (Gen 7で変更されたため)
- ポッポ: 現行=するどいめ/まけんき → 修正後=するどいめのみ (まけんきはGen 4追加)
- ピカチュウ: 隠れ特性ひらいしんを除去 (Gen 5以降の隠れ特性スロットは全て除外)
- ケンタロス: 現行=いかく/いかりのつぼ → 修正後=いかくのみ (いかりのつぼはGen 4追加)

### タイプ相性 (Gen 3 vs 現行の差異)
- フェアリータイプ自体が存在しない (全17タイプ)
- ゴースト → はがね = 0.5倍 (現行は等倍)
- あく → はがね = 0.5倍 (現行は等倍)

### タイプ相性に影響する特性 (data.json内に注釈付き)
| 特性 | 効果 |
|------|------|
| ふゆう (levitate) | じめん技を無効化 |
| ちくでん (volt-absorb) | でんき技を無効化 |
| ちょすい (water-absorb) | みず技を無効化 |
| もらいび (flash-fire) | ほのお技を無効化 |
| あついしぼう (thick-fat) | ほのお・こおり技を半減 |

### data.json スキーマ
```jsonc
{
  "version": "1.0.0",
  "generated_at": "ISO8601",
  "types": {
    "<key>": { "it": "イタリア語名", "color": "#XXXXXX", "text": "white|black" }
  },
  "type_chart": {
    "<attacker_key>": { "<defender_key>": <multiplier> }   // 0, 0.5, 1, 2 のいずれか
  },
  "pokemon": [
    {
      "id": 25,
      "name_ja": "ピカチュウ",
      "name_hira": "ぴかちゅう",
      "types": ["electric"],
      "abilities": ["static"]
    }
  ],
  "abilities": {
    "<key>": {
      "name_ja": "せいでんき",
      "desc_ja": "ゲーム内の説明テキスト",
      "negates": "electric",         // optional: このタイプを無効化
      "halves":  ["fire", "ice"]     // optional: これらのタイプを半減
    }
  }
}
```

## クレジット
データソース: [PokéAPI](https://pokeapi.co/) (CC0 / public-domain風)
