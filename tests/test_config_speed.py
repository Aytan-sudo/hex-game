"""Réglage de vitesse (game/config.py : GameSpeed) et son impact sur les délais."""

import pytest

from game.config import GameSpeed, AISettings, AnimationSettings


def test_default_is_normal():
    s = GameSpeed()
    assert s.name == "Normal"
    assert s.factor == 1.0


def test_names_match_levels():
    assert GameSpeed.names() == ["Lent", "Normal", "Rapide", "Très rapide"]


def test_set_by_name():
    s = GameSpeed()
    s.set_by_name("Rapide")
    assert s.name == "Rapide"
    assert s.factor == 0.45


def test_set_by_name_ignores_unknown():
    s = GameSpeed()
    s.set_by_name("Inexistant")
    assert s.name == "Normal"  # inchangé


def test_cycle_wraps_around():
    s = GameSpeed()
    s.index = len(GameSpeed.LEVELS) - 1
    s.cycle(1)
    assert s.index == 0


def test_delays_scale_with_speed(monkeypatch):
    """
    Les délais effectifs valent base × facteur. On patche le SPEED partagé
    référencé par les propriétés de config.
    """
    import game.config as cfg

    ai = AISettings()
    anim = AnimationSettings()

    monkeypatch.setattr(cfg.SPEED, "index", 1)  # Normal ×1.0
    assert ai.action_delay_ms == ai.base_action_delay_ms
    assert anim.move_step_delay_ms == anim.base_move_step_delay_ms

    cfg.SPEED.set_by_name("Très rapide")  # ×0.2
    assert ai.action_delay_ms == max(1, int(ai.base_action_delay_ms * 0.2))
    assert anim.move_step_delay_ms == max(1, int(anim.base_move_step_delay_ms * 0.2))
