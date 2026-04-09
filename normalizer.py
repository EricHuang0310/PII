# masking/normalizer.py  v3.1（bug-fixed）
"""
Step 0：文字正規化
修正記錄（v3.1）：
  Issue 1 (P0)：調整執行順序，先中文數字→再民國年，確保「民國一一三年」能被正確轉換
  Issue 2 (P0)：補充中文數詞 parser，支援十/百/千結構 + 單數字+時間單位詞
  Issue 6 (P1)：民國年合理範圍從 50–150 擴大為 10–150
  Issue 7 (P2)：_clean_stt_repeats 限縮只壓縮明確語助詞，不再通用壓縮所有中文字

設計說明（Issue 7）：
  純中文數字串（三三三五）仍然會被轉為阿拉伯數字（3335），這是預期行為。
  Presidio 的 regex recognizer 需要辨識阿拉伯數字才能偵測帳號末四碼等欄位。
  語助詞重複（嗯嗯嗯嗯）才是真正需要壓縮的 STT 噪音。
"""

import re
import unicodedata

# ── 1. 全形→半形對照表 ─────────────────────────────────────
_FW_SRC = (
    "\u3000\uff01\uff02\uff03\uff04\uff05\uff06\uff07\uff08\uff09\uff0a\uff0b"
    "\uff0c\uff0d\uff0e\uff0f"
    "\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19"
    "\uff1a\uff1b\uff1c\uff1d\uff1e\uff1f\uff20"
    "\uff21\uff22\uff23\uff24\uff25\uff26\uff27\uff28\uff29\uff2a"
    "\uff2b\uff2c\uff2d\uff2e\uff2f\uff30\uff31\uff32\uff33\uff34"
    "\uff35\uff36\uff37\uff38\uff39\uff3a"
    "\uff3b\uff3c\uff3d\uff3e\uff3f\uff40"
    "\uff41\uff42\uff43\uff44\uff45\uff46\uff47\uff48\uff49\uff4a"
    "\uff4b\uff4c\uff4d\uff4e\uff4f\uff50\uff51\uff52\uff53\uff54"
    "\uff55\uff56\uff57\uff58\uff59\uff5a"
    "\uff5b\uff5c\uff5d\uff5e"
)
_FW_DST = (
    " !\"#$%&'()*+"
    ",-./0123456789"
    ":;<=>?@"
    "ABCDEFGHIJ"
    "KLMNOPQRST"
    "UVWXYZ"
    "[\\]^_`"
    "abcdefghij"
    "klmnopqrst"
    "uvwxyz"
    "{|}~"
)
assert len(_FW_SRC) == len(_FW_DST)
_FULLWIDTH_TABLE   = str.maketrans(_FW_SRC, _FW_DST)
_IDEOGRAPHIC_SPACE = "\u3000"

# ── 2. 中文數字對照表 ─────────────────────────────────────
_ZH_UNIT = {
    "\u96f6": 0, "\u3007": 0,   # 零〇
    "\u4e00": 1, "\u58f9": 1,   # 一壹
    "\u4e8c": 2, "\u8cb3": 2,   # 二貳
    "\u4e09": 3, "\u53c3": 3,   # 三參
    "\u56db": 4, "\u8086": 4,   # 四肆
    "\u4e94": 5, "\u4f0d": 5,   # 五伍
    "\u516d": 6, "\u9678": 6,   # 六陸
    "\u4e03": 7, "\u67d2": 7,   # 七柒
    "\u516b": 8, "\u634c": 8,   # 八捌
    "\u4e5d": 9, "\u7396": 9,   # 九玖
}

_ZH_POS = {
    "\u5341": 10,    # 十
    "\u767e": 100,   # 百
    "\u5343": 1000,  # 千
}

_ALL_ZH_DIGITS = set(_ZH_UNIT.keys()) | set(_ZH_POS.keys())

# Issue 2 修正：匹配含位值單位的中文數詞（七十四、二十六、一百零三等）
_ZH_WITH_POS_RE = re.compile(
    "[" + "".join(re.escape(c) for c in _ALL_ZH_DIGITS) + "]*"
    "[\u5341\u767e\u5343]"   # 必須含十/百/千
    "[" + "".join(re.escape(c) for c in _ALL_ZH_DIGITS) + "]*"
)

# Issue 2 修正：單個中文數字緊接時間單位詞（三月、一日、五號、六點）
_SINGLE_UNIT_RE = re.compile(
    "([" + "".join(re.escape(c) for c in _ZH_UNIT.keys()) + "])"
    "([\u6708\u65e5\u865f\u9ede])"   # 月 日 號 點
)

# 純逐字轉換（連續2+個無位值的中文數字，如一一三→113）
_ZH_CONSECUTIVE_RE = re.compile(
    "[" + "".join(re.escape(c) for c in _ZH_UNIT.keys()) + "]{2,}"
)


def _parse_zh_number(s: str) -> str:
    """解析含位值單位的中文數詞，回傳阿拉伯數字字串。"""
    total = 0
    current = 0
    i = 0
    chars = list(s)

    while i < len(chars):
        c = chars[i]
        if c in _ZH_UNIT:
            current = _ZH_UNIT[c]
            i += 1
        elif c in _ZH_POS:
            pos = _ZH_POS[c]
            if c == "\u5341" and current == 0 and i == 0:
                current = 1   # 「十X」開頭 = 1×10
            total += current * pos
            current = 0
            i += 1
        else:
            break

    total += current
    return str(total) if total > 0 else s


def _zh_digits_to_arabic(text: str) -> str:
    """
    Issue 2 修正：三步驟轉換
    Step A：含位值單位的數詞（七十四→74）
    Step B：單數字+時間單位詞（三月→3月）
    Step C：純逐字連續數字（一一三→113）
    """
    # Step A
    text = _ZH_WITH_POS_RE.sub(lambda m: _parse_zh_number(m.group()), text)
    # Step B
    text = _SINGLE_UNIT_RE.sub(
        lambda m: str(_ZH_UNIT.get(m.group(1), m.group(1))) + m.group(2),
        text
    )
    # Step C
    text = _ZH_CONSECUTIVE_RE.sub(
        lambda m: "".join(str(_ZH_UNIT.get(c, c)) for c in m.group()),
        text
    )
    return text


# ── 3. 民國年轉西元 ───────────────────────────────────────
_ROC_YEAR_RE = re.compile(r"(?:民(?:\u570b|\u56fd)?\s*)(\d{2,3})\s*\u5e74")
_ROC_BASE    = 1911

def _roc_to_ce_year(text: str) -> str:
    """
    Issue 1 修正：中文數字必須先轉換，此函式才能正確處理民國一一三年。
    Issue 6 修正：合理範圍擴大為 10–150（涵蓋民國40–49年的老年客戶）。
    """
    def _replace(m: re.Match) -> str:
        roc = int(m.group(1))
        if 10 <= roc <= 150:
            return f"{roc + _ROC_BASE}\u5e74"
        return m.group()
    return _ROC_YEAR_RE.sub(_replace, text)


# ── 4. STT 語助詞重複壓縮 ─────────────────────────────────
# Issue 7 修正：只壓縮明確語助詞，不做通用壓縮
_STT_FILLER_CHARS = "啊喔嗯欸哦呢吧吼哈呀哎唉那"
_REPEAT_FILLER_RE = re.compile(
    "([" + re.escape(_STT_FILLER_CHARS) + "])" + r"\1{2,}"
)

def _clean_stt_repeats(text: str) -> str:
    """Issue 7 修正：只壓縮明確語助詞的重複（三個以上→兩個）。"""
    return _REPEAT_FILLER_RE.sub(lambda m: m.group(1) * 2, text)


# ── 5. 空白正規化 ─────────────────────────────────────────
_MULTI_SPACE_RE = re.compile(r"\s{2,}")

def _to_halfwidth(text: str) -> str:
    text = text.replace(_IDEOGRAPHIC_SPACE, " ")
    return text.translate(_FULLWIDTH_TABLE)

def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\t", " ")
    return _MULTI_SPACE_RE.sub(" ", text).strip()


# ─────────────────────────────────────────────────────────
def normalize(text: str) -> str:
    """
    主正規化入口。

    執行順序（Issue 1 修正）：
      1. NFC 正規化
      2. 全形→半形
      3. 中文數字→阿拉伯數字（Issue 2：含位值結構 + 時間單位詞）← 必須在民國年之前
      4. 民國年→西元年（此時年份已是阿拉伯數字）
      5. STT 語助詞重複字壓縮（Issue 7：限縮語助詞）
      6. 空白正規化
    """
    if not text:
        return text
    text = unicodedata.normalize("NFC", text)
    text = _to_halfwidth(text)
    text = _zh_digits_to_arabic(text)   # Issue 1：先轉中文數字
    text = _roc_to_ce_year(text)
    text = _clean_stt_repeats(text)
    text = _normalize_whitespace(text)
    return text
