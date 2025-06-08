"""
홈 화면 & 공통 라우트
"""
import sys # Added for logging
from flask import Blueprint, render_template, session, redirect, request, url_for
from app.utils.i18n import get_locale

home_bp = Blueprint("home", __name__)

# ────────────────────────────────────────────────
# 템플릿 전역 변수 — {{ font_size }} 로 사용
# ────────────────────────────────────────────────
@home_bp.context_processor
def inject_globals():
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.inject_globals(args={{_func_args}})")
    lang = session.get("lang", "ko")
    return dict(
        font_size=session.get("font_size", "normal"),
        lang=lang,
        locale=get_locale(lang),        # ← locale dict 주입
    )

# ────────────────────────────────────────────────
# 홈 화면
# ────────────────────────────────────────────────
@home_bp.route("/")
def index():
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.index(args={{_func_args}})")
    return render_template("home.html")

# ────────────────────────────────────────────────
# 글꼴 크기 변경: /font/<size>
# ────────────────────────────────────────────────
@home_bp.route("/font/<size>")
def set_font(size: str):
    """
    <size> : small | normal | large
    """
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.set_font(args={{_func_args}})")
    if size in {"small", "normal", "large"}:
        session["font_size"] = size
    # 직전 페이지로 돌아가거나 없으면 홈으로
    return redirect(request.referrer or url_for("home.index"))

# ───── (선택) 언어 전환 · TTS · 긴급 호출 라우트 예시 ─────
@home_bp.route("/switch-language")
def switch_language():
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.switch_language(args={{_func_args}})")
    session["lang"] = "en" if session.get("lang") == "ko" else "ko"
    return redirect(request.referrer or url_for("home.index"))

@home_bp.route("/emergency")
def emergency():
    _func_args = locals()
    _module_path = sys.modules[__name__].__name__ if __name__ in sys.modules else __file__
    print(f"ENTERING: {_module_path}.emergency(args={{_func_args}})")
    return render_template("emergency.html")
