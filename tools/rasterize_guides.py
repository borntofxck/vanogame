"""PNG-проверка DOCX через штатный renderer и PDF, экспортированный Word.

Windows-сборка runtime не содержит LibreOffice. Меняется только этап
convert_to_pdf; растеризация и размер страниц остаются у packaged render_docx.
"""
import importlib.util
from pathlib import Path
import os
import shutil

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path('C:/Users/Getsu/.cache/codex-runtimes/codex-primary-runtime/dependencies')
RENDERER = Path('C:/Users/Getsu/.codex/plugins/cache/openai-primary-runtime/documents/26.905.11957/skills/documents/render_docx.py')


def main():
    os.environ['PATH'] = str(RUNTIME / 'native/poppler/Library/bin') + os.pathsep + os.environ['PATH']
    spec = importlib.util.spec_from_file_location('packaged_render_docx', RENDERER)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    for title, stem in [('Руководство_по_защите_byVanoGame', 'handbook'), ('Короткая_речь_и_шпаргалка_byVanoGame', 'speech')]:
        exported_pdf = ROOT / 'artifacts/word-qa' / f'{stem}.pdf'
        if not exported_pdf.exists():
            raise FileNotFoundError(exported_pdf)

        def use_word_pdf(docx_path, user_profile, out_dir, basename, **kwargs):
            destination = Path(out_dir) / f'{basename}.pdf'
            shutil.copyfile(exported_pdf, destination)
            return str(destination), 'Converted by Microsoft Word COM on Windows'

        renderer.convert_to_pdf = use_word_pdf
        renderer.rasterize(str(ROOT / 'submission' / f'{title}.docx'),
                           str(ROOT / 'artifacts/word-qa' / stem), 125,
                           verbose=False, emit_pdf=False)
        print(stem + ': PNG rendered with packaged render_docx')


if __name__ == '__main__':
    main()
