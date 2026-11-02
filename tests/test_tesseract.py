import os
import subprocess

import pytest

from step1_ocr import extractor


def _erro_elevacao():
    e = OSError("A operação solicitada requer elevação")
    e.winerror = 740
    return e


@pytest.fixture
def windows_sem_tesseract(monkeypatch, tmp_path):
    monkeypatch.setattr(extractor.platform, "system", lambda: "Windows")
    monkeypatch.setattr(extractor.shutil, "which", lambda _: None)
    monkeypatch.setenv("TEMP", str(tmp_path))
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        monkeypatch.setenv(var, str(tmp_path / var))
    return tmp_path


def test_pede_elevacao_quando_instalador_exige_admin(windows_sem_tesseract, monkeypatch):
    chamadas = []
    destino = windows_sem_tesseract / "ProgramFiles" / "Tesseract-OCR" / "tesseract.exe"

    def run(cmd, check):
        chamadas.append(cmd[0])
        if cmd[0].endswith("tesseract_setup.exe"):
            raise _erro_elevacao()
        if cmd[0] == "powershell":
            assert "-Verb RunAs" in cmd[-1]
            destino.parent.mkdir(parents=True)
            destino.write_text("")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(extractor.subprocess, "run", run)
    assert extractor.verificar_tesseract() is True
    assert chamadas == ["curl", os.path.join(str(windows_sem_tesseract), "tesseract_setup.exe"), "powershell"]
    assert extractor.pytesseract.pytesseract.tesseract_cmd == str(destino)


def test_nao_quebra_se_usuario_recusa_elevacao(windows_sem_tesseract, monkeypatch):
    def run(cmd, check):
        if cmd[0].endswith("tesseract_setup.exe"):
            raise _erro_elevacao()
        if cmd[0] == "powershell":
            raise subprocess.CalledProcessError(1, cmd)  # UAC recusado
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(extractor.subprocess, "run", run)
    assert extractor.verificar_tesseract() is False


def test_encontra_instalacao_por_usuario(windows_sem_tesseract):
    exe = windows_sem_tesseract / "LOCALAPPDATA" / "Programs" / "Tesseract-OCR" / "tesseract.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    assert extractor.verificar_tesseract() is True
