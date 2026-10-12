"""User-editable mnemonic aliases."""

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from innopetrol.model import mnemonics
from innopetrol.model.well import Curve


def test_user_alias_is_recognized_and_wins(testdata_well):
    assert mnemonics.family_of("GAMMA_API") is None
    mnemonics.set_user_aliases({"gamma_ray": ["gamma_api"], "medium_res": ["RT"], "nonsense": ["X"]})
    assert mnemonics.family_of("GAMMA_API") == "gamma_ray"
    assert mnemonics.family_of("RT") == "medium_res"  # moved from deep resistivity
    assert mnemonics.user_aliases() == {"gamma_ray": ["GAMMA_API"], "medium_res": ["RT"]}
    w = testdata_well
    w.add_curve(Curve("GAMMA_API", "GAPI", "", np.full_like(w.depth, 50.0)))
    w.remove_curve("SGR")
    assert mnemonics.find_curve(w, "gamma_ray") == "GAMMA_API"
    mnemonics.set_user_aliases({})
    assert mnemonics.family_of("RT") == "deep_res"


def test_conflicts_and_file_round_trip():
    aliases = {"gamma_ray": ["GX", "gr2"], "sp": ["gx"]}
    assert mnemonics.alias_conflicts(aliases) == [("GX", ["gamma_ray", "sp"])]
    assert mnemonics.aliases_from_json(mnemonics.aliases_to_json(aliases)) == aliases
    with pytest.raises(ValueError):
        mnemonics.aliases_from_json('{"format": "other"}')


def test_dialog_and_settings(qtbot, tmp_path, monkeypatch):
    from innopetrol.ui import aliases_dialog
    from innopetrol.ui.main_window import MainWindow

    settings = QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)
    w = MainWindow(settings)
    qtbot.addWidget(w)

    def fake_exec(dialog):
        row = dialog.keys.index("gamma_ray")
        dialog.table.item(row, aliases_dialog.COL_USER).setText("GRX; GR_COMPANY")
        return True

    monkeypatch.setattr(aliases_dialog.AliasesDialog, "exec", fake_exec)
    w.edit_aliases()
    assert mnemonics.family_of("GR_COMPANY") == "gamma_ray"
    mnemonics.set_user_aliases({})
    again = MainWindow(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat))  # restored at start
    qtbot.addWidget(again)
    assert mnemonics.family_of("GRX") == "gamma_ray"


def test_dialog_rejects_conflicts(qtbot, no_modal_boxes):
    from innopetrol.ui.aliases_dialog import COL_USER, AliasesDialog

    d = AliasesDialog()
    qtbot.addWidget(d)
    d.table.item(d.keys.index("gamma_ray"), COL_USER).setText("ABC")
    d.table.item(d.keys.index("sp"), COL_USER).setText("abc")
    d._ok()
    assert d.result() == 0 and "ABC" in no_modal_boxes[-1][1][2]
