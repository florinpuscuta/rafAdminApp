"""Teste pentru rendering-ul template-urilor de email (HTML)."""
from __future__ import annotations

import pytest

from app.core.email import _render_html


def test_render_html_contains_required_fields():
    out = _render_html(
        title="Test titlu",
        intro="Acesta e un mesaj de test.",
        cta_label="Click aici",
        cta_url="https://example.com/reset?token=abc",
        footer="Expiră în 30 min.",
    )
    assert "<!DOCTYPE html>" in out
    assert "Test titlu" in out
    assert "Acesta e un mesaj de test." in out
    assert "Click aici" in out
    assert "https://example.com/reset?token=abc" in out
    # Footer-ul e afișat
    assert "Expiră în 30 min." in out
    # Header-ul de brand e prezent
    assert "Adeplast SaaS" in out


def test_render_html_escapes_dangerous_input():
    """Input-ul user-controlled (invitator email, link) trebuie escape-uit."""
    out = _render_html(
        title='Nume cu <script>',
        intro='intro cu "ghilimele" și & amp',
        cta_label="btn",
        cta_url='https://example.com/?x="evil"&y=<z>',
        footer="footer normal",
    )
    # <script> nu apare literal — escape-uit la &lt;script&gt;
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    # Ghilimelele raw nu se propagă în atributul href
    assert 'href="https://example.com/?x=\"evil\"' not in out
    # URL-ul apare în formă escape-uită
    assert "&quot;evil&quot;" in out or "&#x27;evil" in out or "&#34;evil" in out


def test_render_html_preserves_linebreaks_in_intro():
    out = _render_html(
        title="t",
        intro="linia 1\nlinia 2",
        cta_label="btn",
        cta_url="https://example.com",
        footer="f",
    )
    # \n → <br>
    assert "linia 1<br>linia 2" in out


@pytest.mark.asyncio
async def test_send_falls_back_to_log_without_smtp_host(caplog):
    """Fără SMTP_HOST setat, _send doar loghează (nu aruncă)."""
    from app.core.email import _send

    with caplog.at_level("WARNING", logger="adeplast.email"):
        await _send(
            to_email="foo@example.com",
            subject="s",
            text_body="corp text",
            html_body="<p>corp html</p>",
        )
    msgs = [r.getMessage() for r in caplog.records]
    assert any("EMAIL-DEV" in m and "foo@example.com" in m for m in msgs)
