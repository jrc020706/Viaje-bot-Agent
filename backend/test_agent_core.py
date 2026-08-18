"""Focused tests for ViajeBot routing and session travel preferences."""

from agent_core import (
    GROQ_FAST_MODEL,
    GROQ_THINKING_MODEL,
    _select_agent,
    _travel_profiles,
    _pending_profile_updates,
    _update_travel_profile,
)


def setup_function():
    """Keep session memory isolated between tests."""
    _travel_profiles.clear()
    _pending_profile_updates.clear()


def test_complex_visual_request_uses_thinking_model():
    selection = _select_agent("Crea un itinerario de 5 dias en Cartagena con presupuesto y fotos")

    assert selection.model == GROQ_THINKING_MODEL
    assert selection.intent == "planning"


def test_simple_visual_request_uses_fast_model():
    selection = _select_agent("Muestrame fotos de Cartagena")

    assert selection.model == GROQ_FAST_MODEL
    assert selection.intent == "visual"


def test_currency_request_uses_fast_model():
    selection = _select_agent("Convierte 100 USD a COP")

    assert selection.model == GROQ_FAST_MODEL
    assert selection.intent == "currency"


def test_profile_change_requires_confirmation_before_replacement():
    profile, pending, confirmed = _update_travel_profile("profile-test", "Mi presupuesto es 2.000.000 COP")
    assert profile["presupuesto"] == "2.000.000 COP"
    assert not pending
    assert not confirmed

    profile, pending, confirmed = _update_travel_profile("profile-test", "Mi presupuesto es 3.000.000 COP")
    assert profile["presupuesto"] == "2.000.000 COP"
    assert pending["presupuesto"] == "3.000.000 COP"
    assert not confirmed

    profile, pending, confirmed = _update_travel_profile("profile-test", "Si")
    assert profile["presupuesto"] == "3.000.000 COP"
    assert not pending
    assert confirmed


def test_new_preference_is_saved_while_another_change_waits_for_confirmation():
    _update_travel_profile("mixed-profile-test", "Mi presupuesto es 2.000.000 COP")

    profile, pending, confirmed = _update_travel_profile(
        "mixed-profile-test", "Mi presupuesto es 3.000.000 COP para 5 dias"
    )

    assert profile["presupuesto"] == "2.000.000 COP"
    assert profile["duracion"] == "5 dias"
    assert pending["presupuesto"] == "3.000.000 COP"
    assert not confirmed
