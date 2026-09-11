from streamlit.testing.v1 import AppTest


def generate_page():
    from services.ui.app import render_generate_page
    from unittest.mock import MagicMock

    render_generate_page(MagicMock())


def test_nfl_controls_rerun_before_form_submit():
    app = AppTest.from_function(generate_page).run()
    assert not app.exception
    app.selectbox(key="gen_sport").select("NFL").run()
    assert not app.exception
    assert "moneyline" in app.multiselect(key="gen_nfl_markets_All").value
    app.selectbox(key="gen_nfl_group").select("Game bets").run()
    assert app.multiselect(key="gen_nfl_markets_Game bets").value == [
        "moneyline",
        "spread",
        "total",
    ]
    app.selectbox(key="gen_nfl_group").select("Player props").run()
    assert len(app.multiselect(key="gen_nfl_markets_Player props").value) == 7
    assert not app.exception
