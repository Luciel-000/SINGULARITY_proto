"""
============================================================
  core/dialogue_data.py  ── 会話データ定義  [0.7 新規]

  担当:
  - ゲーム内の会話（NPC・観測補助機構・イベント）のテキストを一元管理
    - 会話ID で引いて「話者名・セリフリスト・終了後イベント」を返す
    - 不正な会話IDでもフォールバックして落ちない安全設計

  ── 会話辞書の構造 ─────────────────────────────────────
  DIALOGUE_DATA["会話ID"] = {
      "speaker" : 話者名（ウィンドウ上部に表示する名前）
      "lines"   : セリフ文字列のリスト（1要素 = 1ページ）
      "on_end"  : 会話終了後に発火するイベントID（不要な場合は None）
                  例: "sage_activate" → 観測補助機構起動会話を続けて開始
  }

  ── 現在定義されている会話 ───────────────────────────────
    "elder_first"  : 謎の老人との初回会話（観測補助機構起動の引き金）
    "elder_repeat" : 謎の老人との2回目以降の会話
    "sage_boot"    : 観測補助機構初回起動イベント

  ── 将来の拡張方法 ──────────────────────────────────────
    新しい会話を追加するには:
      1. DIALOGUE_DATA に新しいエントリを追加するだけ
      2. npc.py で dialogue_id に割り当てる
      3. on_end に別の会話IDを指定すると連鎖会話になる
    例:
      "shopkeeper" : { "speaker": "商人", "lines": [...], "on_end": None }
      "gate_guard" : { "speaker": "門番", "lines": [...], "on_end": None }

  ── 他ファイルとの依存関係 ──────────────────────────────
    - 他の core ファイルを一切 import しない
      （循環 import を防ぐため）
    - npc.py / game.py からインポートされる予定

  ── 使い方 ──────────────────────────────────────────────
    from core.dialogue_data import (
        get_dialogue, get_dialogue_lines,
        get_dialogue_speaker, get_dialogue_on_end,
        is_valid_dialogue,
    )

    lines   = get_dialogue_lines("elder_first")
    speaker = get_dialogue_speaker("elder_first")  # → "謎の老人"
    on_end  = get_dialogue_on_end("elder_first")   # → "sage_activate"

    # 不正IDでも落ちない
    lines   = get_dialogue_lines("unknown")        # → ["……"]
============================================================
"""


# ── フォールバック用データ ──────────────────────────────
# 不正な会話IDが渡されたとき、これを返す
_FALLBACK_DIALOGUE: dict = {
    "speaker": "???",
    "lines"  : ["……"],
    "on_end" : None,
}


# ── 会話データ辞書 ──────────────────────────────────────
#
# ★ 新しい会話を追加するときはここにエントリを追記するだけ！
#
DIALOGUE_DATA: dict[str, dict] = {

    # ──────────────────────────────────────────────────
    #  プロローグ：ゲーム開始直後の導入
    #  on_end = "sage_activate" → 会話終了後に観測補助機構起動
    # ──────────────────────────────────────────────────
    "prologue_intro": {
        "speaker": "",
        "lines"  : [
            "暗闇の中、誰かの祈りがこだまする。",
            "それは名もなき祈り。",
            "失われたものを、もう一度つなぎ止めようとする小さな願いだった。",
            "そして、その祈りに世界の叡智が反応する。",
        ],
        "on_end" : "sage_activate",
    },

    "elder_first": {
        "speaker": "謎の老人",
        "lines"  : [
            "……目が覚めたか。",
            "お前が何者かは、まだ誰も知らぬ。",
            "だが、その身には不思議な空白がある。",
            "町の外には魔物がいる。無理はするな。",
        ],
        # 会話終了後は通常に探索へ戻る
        "on_end" : None,
    },

    # ──────────────────────────────────────────────────
    #  謎の老人：2回目以降の会話
    #  初回フラグ（talked=True）になったあとはこちらを使う
    # ──────────────────────────────────────────────────
    "elder_repeat": {
        "speaker": "謎の老人",
        "lines"  : [
            "外へ出るなら、草原の魔物に気をつけるのだ。",
            "自分を知りたければ、まず世界を見よ。",
        ],
        "on_end" : None,
    },

    # ──────────────────────────────────────────────────
    #  観測補助機構：初回起動イベント
    #  elder_first の on_end = "sage_activate" から呼ばれる
    #  ノービスの識別・属性解析システムの起動を演出する
    # ──────────────────────────────────────────────────
    "elder_after_sage": {
        "speaker": "隰弱・閠∽ｺｺ",
        "lines"  : [
            "……妙な気配をまとっているな。",
            "お前の内側に、何かが目覚めたのかもしれん。",
            "焦るな。まずはこの村の外を見てくるといい。",
        ],
        "on_end" : None,
    },

    "elder_after_battle": {
        "speaker": "隰弱・閠∽ｺｺ",
        "lines"  : [
            "外の魔物と戦ったようだな。",
            "恐れずに立ち向かったなら、それもまた一つの選択だ。",
            "その選択の積み重ねが、お前の道を形作る。",
        ],
        "on_end" : None,
    },

    "elder_after_quest_done": {
        "speaker": "髫ｰ蠑ｱ繝ｻ髢竏ｽ・ｺ・ｺ",
        "lines"  : [
            "よく戻ったな。",
            "外の魔物を退けたのなら、少しはこの地の危うさも見えただろう。",
            "だが、これは始まりにすぎん。焦らず進め。",
        ],
        "on_end" : None,
    },

    "elder_after_report": {
        "speaker": "謎の老人",
        "lines"  : [
            "少しは落ち着いた顔になったな。",
            "この村の北には、古い祠へ続く道がある。",
            "無理はするな。だが、進むなら覚悟を持て。",
        ],
        "on_end" : None,
    },

    "elder_after_go_north_reached": {
        "speaker": "謎の老人",
        "lines"  : [
            "北の方へ向かったのか。",
            "ならば、お前も感じただろう。あの辺りの空気の重さを。",
            "まだ深入りはするな。準備を整えてから進め。",
        ],
        "on_end" : None,
    },

    "sage_boot": {
        "speaker": "《観測補助機構》",
        "lines"  : [
            "《世界の叡智が、名もなき祈りに反応しています》",
            "《祈祷因子を確認》",
            "《叡智記録層と同期》",
            "compile...",
            "《成功しました》",
            "祈りと叡智の融合により、未完成の観測補助機構が生成されました。",
            "この機構は、世界情報の観測・解析・戦闘補助を目的とします。",
            "個体識別名：未設定。",
            "この存在に、名前を与えてください。",
        ],
        "on_end" : None,
    },

    # ──────────────────────────────────────────────────
    #  以下は将来追加予定（コメントで設計を残しておく）
    # ──────────────────────────────────────────────────

    # "shopkeeper": {
    #     "speaker": "商人",
    #     "lines"  : [
    #         "いらっしゃい。何かお探しかい？",
    #         "今は品揃えが少ないが、また来てくれ。",
    #     ],
    #     "on_end" : None,
    # },

    # "gate_guard": {
    #     "speaker": "門番",
    #     "lines"  : [
    #         "草原への道か。魔物が出るから気をつけろよ。",
    #     ],
    #     "on_end" : None,
    # },
}


# ── 公開関数 ───────────────────────────────────────────

def is_valid_dialogue(dialogue_id: str) -> bool:
    """
    会話IDが存在するか確認する。

    使用例:
        is_valid_dialogue("elder_first")  → True
        is_valid_dialogue("unknown")      → False
    """
    return dialogue_id in DIALOGUE_DATA


def get_dialogue(dialogue_id: str) -> dict:
    """
    会話IDから会話データ辞書をまるごと返す。
    存在しないIDはフォールバック（{"speaker":"???","lines":["……"],"on_end":None}）。

    使用例:
        d = get_dialogue("elder_first")
        print(d["speaker"])   # → "謎の老人"
        print(d["lines"])     # → ["……目が覚めたか。", ...]
    """
    return DIALOGUE_DATA.get(dialogue_id, _FALLBACK_DIALOGUE)


def get_dialogue_lines(dialogue_id: str) -> list[str]:
    """
    会話IDからセリフリストを返す。
    各要素が会話ウィンドウの1ページに対応する。

    使用例:
        lines = get_dialogue_lines("elder_first")
        # → ["……目が覚めたか。", "お前が何者かは…", ...]

        lines = get_dialogue_lines("unknown")
        # → ["……"]  ← フォールバック
    """
    return get_dialogue(dialogue_id)["lines"]


def get_dialogue_speaker(dialogue_id: str) -> str:
    """
    会話IDから話者名を返す。
    会話ウィンドウの上部に表示する名前として使う。

    使用例:
        get_dialogue_speaker("elder_first")  → "謎の老人"
        get_dialogue_speaker("sage_boot")    → "《観測補助機構》"
        get_dialogue_speaker("unknown")      → "???"
    """
    return get_dialogue(dialogue_id)["speaker"]


def get_dialogue_on_end(dialogue_id: str) -> str | None:
    """
    会話終了後に発火するイベントIDを返す。
    イベントなしの場合は None を返す。

    game.py が会話終了時にこれを参照して連鎖会話やフラグ処理を行う。

    使用例:
        get_dialogue_on_end("elder_first")   → "sage_activate"
        get_dialogue_on_end("elder_repeat")  → None
        get_dialogue_on_end("sage_boot")     → None
        get_dialogue_on_end("unknown")       → None
    """
    return get_dialogue(dialogue_id).get("on_end")


def all_dialogue_ids() -> list[str]:
    """
    全会話IDのリストを返す（デバッグ・確認用）。

    使用例:
        all_dialogue_ids()
        # → ["elder_first", "elder_repeat", "sage_boot"]
    """
    return list(DIALOGUE_DATA.keys())
