import re
from dataclasses import dataclass
from typing import Optional
from ..state import IntentOutput


INTENT_RULES = [
    ("wrong_item", 0.97, "wrong_item_explicit",
     re.compile(
         r"\b(wrong|incorrect|different|not what i ordered|not the (right|correct)|"
         r"sent me (a |the )?(wrong|different)|ordered .{0,30} got|"
         r"expected .{0,30} received|substitut(ed|ion)|"
         r"galat (item|cheez|product)|jo manga .{0,20} nahi aaya)\b",
         re.IGNORECASE
     )),
    ("missing_item", 0.96, "missing_item_explicit",
     re.compile(
         r"\b(miss(ing|ed)|not (in|inside) (the )?(bag|box|package|order)|"
         r"(one|some|an?) item.{0,20}(short|missing|not (there|included|found))|"
         r"incomplete (order|delivery)|item(s)? (not |were )?(receiv|deliver|includ)|"
         r"(bag|box) (mein|me) .{0,20} nahi (tha|thi|the)|"
         r"cheez (nahi|missing) (thi|tha)|poora order nahi)\b",
         re.IGNORECASE
     )),
    ("not_delivered", 0.97, "not_delivered_explicit",
     re.compile(
         r"\b(not (delivered|arrived|received|here)|never (got|received|arrived)|"
         r"didn'?t (arrive|come|deliver|receive)|order (not|never) (came|arrived|delivered)|"
         r"still (waiting|not received|not arrived|havent got)|"
         r"where (is|are) (my|the) (order|package|parcel|delivery)|"
         r"delivery (not|never) (done|arrived|came)|"
         r"nahi (mila|aayi|aaya|pahuncha)|deliver nahi|"
         r"order abhi tak nahi|kahan hai mera order)\b",
         re.IGNORECASE
     )),
    ("damaged", 0.96, "damaged_explicit",
     re.compile(
         r"\b(broken?|cracked?|crushed?|damaged?|shattered?|torn?|leaking?|leaked?|"
         r"dented?|smashed?|busted?|tampered?|open(ed)? (box|package|seal)|"
         r"seal (broken|tampered|open)|not working|stopped working|dead on arrival|"
         r"defective|faulty|malfunctioning|doesn'?t work|"
         r"toot(a|i|e)|phoot(a|i|e)|kharab (hua|hai|nikla)|"
         r"damage (hua|nikla)|pack(aging)? (kharab|phati|toot))\b",
         re.IGNORECASE
     )),

    # ── QUALITY ISSUE
    ("quality", 0.95, "quality_explicit",
     re.compile(
         r"\b(stale|expired?|expiry|rotten?|mold(y|ed)?|bad (quality|smell|taste)|"
         r"not fresh|poor quality|low quality|horrible (taste|quality|smell)|"
         r"inedible|uneat(able|en)?|smells? (bad|awful|terrible|weird)|"
         r"tastes? (bad|awful|terrible|weird|off)|"
         r"(food|product) (was |is )?(bad|terrible|awful|disgusting)|"
         r"baasi|sada hua|kharab (khana|maal|product)|"
         r"ganda (mila|nikla|tha)|bura (taste|smell|laga))\b",
         re.IGNORECASE
     )),

    # ── REFUND INQUIRY (policy / status check — not a new claim)
    ("refund_inquiry", 0.94, "refund_inquiry_explicit",
     re.compile(
         r"\b(refund (policy|status|update|timeline|when|how long)|"
         r"when (will|do) (i|we) (get|receive) (the |my )?refund|"
         r"track(ing)? (my )?refund|where is my refund|"
         r"how (long|many days) (for|does|will) (refund|money)|"
         r"refund (process|procedure|rules?)|"
         r"paisa (kab|kaise|status)|refund kab milega|"
         r"paise wapas (kab|status)|refund track)\b",
         re.IGNORECASE
     )),
    ("request_refund", 0.92, "refund_request_generic",
     re.compile(
         r"\b(want (a |my )?refund|need (a |my )?refund|request(ing)? (a )?refund|"
         r"give (me|us) (a |my )?refund|(please |kindly )?refund (me|my|the)|"
         r"money back|get my money back|return (the )?money|"
         r"charg(ed|eback)|dispute (the )?charge|"
         r"paisa wapas (chahiye|karo|do)|refund chahiye|"
         r"paise wapas|mujhe refund|wapas karo)\b",
         re.IGNORECASE
     )),
    ("cancel_order", 0.95, "cancel_order_explicit",
     re.compile(
         r"\b(cancel (my |the |this )?(order|item)|order cancel(led|ation)?|"
         r"want to cancel|need to cancel|please cancel|stop (my |the )?order|"
         r"order (band|cancel) (karo|karna|chahiye)|"
         r"order roko|cancel kar do)\b",
         re.IGNORECASE
     )),
    ("late_delivery", 0.93, "late_delivery_explicit",
     re.compile(
         r"\b(late (delivery|order|shipment)|delayed?|taking (too |very )?long|"
         r"estimated (delivery|time|date) (passed|missed|wrong)|"
         r"(more than|over) (1|2|3|one|two|three) (day|hour|hr)s?|"
         r"still (not|hasn'?t) (arrived?|delivered?|come)|"
         r"bahut (der|time) (ho|lag) (gaya|raha)|"
         r"late (aa raha|hua|ho gaya)|der se)\b",
         re.IGNORECASE
     )),
]


def regex_classify(message: str) -> Optional[IntentOutput]:
    for label, confidence, rule_name, pattern in INTENT_RULES:
        if pattern.search(message):
            return IntentOutput(
                intent=label,
                confidence=confidence,
                reason_category=rule_name,
                order_id=None
            )
    return None 



