#!/usr/bin/env python3
from __future__ import annotations

import cgi
import html
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from urllib.parse import parse_qs, urlparse
from urllib.parse import quote
import uuid

ROOT = Path(__file__).resolve().parent
WORK_ROOT = ROOT / "work"
SCRIPTS_DIR = ROOT.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from folder_to_manual_duplex import collect_supported_files, convert_all  # noqa: E402
from manual_duplex_pdf import build_passes_from_paths  # noqa: E402


INDEX_HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def content_disposition_value(disposition: str, filename: str) -> str:
    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii") or "document.pdf"
    encoded = quote(filename)
    return f"{disposition}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"


class ManualDuplexHandler(BaseHTTPRequestHandler):
    server_version = "ManualDuplexHTTP/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_html(INDEX_HTML)
            return

        if parsed.path == "/file":
            self._serve_file(parsed)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Page not found")

    def do_POST(self) -> None:
        if self.path == "/prepare":
            self._handle_prepare()
            return

        if self.path == "/finalize":
            self._handle_finalize()
            return

        if self.path == "/shutdown":
            self._handle_shutdown()
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Page not found")

    def _handle_prepare(self) -> None:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            },
        )

        file_items = form["source"] if "source" in form else None
        if file_items is None:
            self._send_error_page("没有收到文件。")
            return

        if not isinstance(file_items, list):
            file_items = [file_items]

        valid_items = [item for item in file_items if getattr(item, "filename", "")]
        if not valid_items:
            self._send_error_page("没有收到文件。")
            return

        source_names = []
        stored_roots = []

        job_id = uuid.uuid4().hex[:12]
        job_dir = WORK_ROOT / job_id
        input_dir = job_dir / "input"
        output_dir = job_dir / "output"
        converted_dir = output_dir / "converted-pdfs"
        input_dir.mkdir(parents=True, exist_ok=True)
        converted_dir.mkdir(parents=True, exist_ok=True)

        for index, file_item in enumerate(valid_items, start=1):
            raw_name = file_item.filename.replace("\\", "/")
            relative_parts = [part for part in Path(raw_name).parts if part not in ("", ".", "..")]
            if not relative_parts:
                continue

            source_names.append(relative_parts[-1])
            input_path = input_dir / f"{index:03d}"
            for part in relative_parts:
                input_path /= part
            input_path.parent.mkdir(parents=True, exist_ok=True)
            with input_path.open("wb") as handle:
                shutil.copyfileobj(file_item.file, handle)
            top_level_root = input_dir / f"{index:03d}"
            if top_level_root not in stored_roots:
                stored_roots.append(top_level_root)

        if not source_names:
            shutil.rmtree(job_dir, ignore_errors=True)
            self._send_error_page("没有收到有效文件。")
            return

        try:
            sources = collect_supported_files(stored_roots, job_dir / "_temp")
            if not sources:
                raise ValueError("没有找到可处理的文件。")
            converted = convert_all(sources, converted_dir)
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(job_dir, ignore_errors=True)
            self._send_error_page(f"预处理失败：{exc}")
            return

        page = self._order_page(
            job_id=job_id,
            source_names=source_names,
            converted_names=[path.name for path in converted],
        )
        self._send_html(page)

    def _handle_finalize(self) -> None:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            },
        )

        job_id = form.getfirst("job_id", "").strip()
        if not job_id:
            self._send_error_page("缺少任务编号。")
            return

        job_dir = WORK_ROOT / job_id
        output_dir = job_dir / "output"
        converted_dir = output_dir / "converted-pdfs"
        if not converted_dir.is_dir():
            self._send_error_page("找不到待排序的转换结果，请重新上传。")
            return

        order_items = form["ordered_file"] if "ordered_file" in form else None
        if order_items is None:
            self._send_error_page("没有收到排序结果。")
            return

        if isinstance(order_items, list):
            ordered_names = [item.value for item in order_items]
        else:
            ordered_names = [order_items.value]

        ordered_names = [Path(name).name for name in ordered_names if name]
        if not ordered_names:
            self._send_error_page("排序列表为空。")
            return

        ordered_paths = [converted_dir / name for name in ordered_names]
        if any(not path.is_file() for path in ordered_paths):
            self._send_error_page("排序列表里有文件不存在，请重新上传。")
            return

        prefix = Path(ordered_names[0]).stem if len(ordered_names) == 1 else "mixed-batch"
        try:
            merged_path, odd_path, even_path, total_pages = build_passes_from_paths(
                ordered_paths,
                output_dir / "manual-duplex",
                prefix,
                keep_document_boundaries=True,
            )
        except Exception as exc:  # noqa: BLE001
            self._send_error_page(f"生成打印文件失败：{exc}")
            return

        self._reveal_in_finder(output_dir)

        page = self._result_page(
            job_id=job_id,
            source_names=ordered_names,
            converted_names=[path.name for path in ordered_paths],
            total_pages=int(total_pages),
            merged_name=merged_path.name,
            odd_name=odd_path.name,
            even_name=even_path.name,
        )
        self._send_html(page)

    def _handle_shutdown(self) -> None:
        page = """<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>助手已关闭</title>
<style>
  body {
    margin: 0;
    min-height: 100vh;
    display: grid;
    place-items: center;
    background: linear-gradient(160deg, #efe5d3 0%, #f8f2e8 46%, #eadbc1 100%);
    color: #2b2117;
    font-family: 'Iowan Old Style', 'Palatino Linotype', 'PingFang SC', serif;
    padding: 28px;
  }
  .panel {
    width: min(620px, 100%);
    background: rgba(255, 251, 244, 0.92);
    border: 1px solid rgba(87, 54, 22, 0.14);
    border-radius: 28px;
    padding: 32px;
    box-shadow: 0 24px 60px rgba(76, 49, 21, 0.14);
  }
  h1 { margin: 0 0 10px; font-size: clamp(2rem, 5vw, 3rem); }
  p { line-height: 1.7; }
  .hint {
    display: inline-block;
    margin-top: 18px;
    padding: 14px 16px;
    border-radius: 16px;
    background: rgba(161, 77, 0, 0.08);
  }
</style>
<div class="panel">
  <h1>双面打印助手已关闭</h1>
  <p>本地网页服务已经准备停止。下次需要时，重新双击 `双面打印助手.app` 就可以再打开。</p>
  <div class="hint">这个页面几秒后就会失去连接，属于正常现象。</div>
</div>
</html>"""
        self._send_html(page)
        control_script = ROOT.parent / "scripts" / "webapp-control.sh"
        shutdown_cmd = (
            f"sleep 1; {shlex.quote(str(control_script))} stop >/dev/null 2>&1"
        )
        subprocess.Popen(
            ["/bin/sh", "-lc", shutdown_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _page_actions(self) -> str:
        return """
<div class="top-actions">
  <form method="post" action="/shutdown">
    <button class="shutdown" type="submit">关闭助手</button>
  </form>
</div>
"""

    def _order_page(self, *, job_id: str, source_names: list[str], converted_names: list[str]) -> str:
        source_label = "、".join(source_names[:4])
        if len(source_names) > 4:
            source_label += f" 等 {len(source_names)} 个文件"
        items = "".join(
            f'<li class="sort-item" draggable="true" data-name="{html.escape(name)}">'
            f'<span class="grab">⋮⋮</span><span>{html.escape(name)}</span>'
            f'<input type="hidden" name="ordered_file" value="{html.escape(name)}"></li>'
            for name in converted_names
        )
        return f"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>手动排序</title>
<style>
  :root {{
    --bg: #f4ecdd;
    --ink: #2b2117;
    --accent: #a14d00;
    --panel: rgba(255, 251, 244, 0.92);
    --line: rgba(87, 54, 22, 0.14);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    min-height: 100vh;
    background:
      radial-gradient(circle at top right, rgba(255, 214, 153, 0.45), transparent 30%),
      linear-gradient(160deg, #efe5d3 0%, #f8f2e8 46%, #eadbc1 100%);
    color: var(--ink);
    font-family: 'Iowan Old Style', 'Palatino Linotype', 'PingFang SC', serif;
    display: grid;
    place-items: center;
    padding: 28px;
  }}
  .panel {{
    width: min(860px, 100%);
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 28px;
    padding: 32px;
    box-shadow: 0 24px 60px rgba(76, 49, 21, 0.14);
  }}
  .top-actions {{
    display: flex;
    justify-content: flex-end;
    margin-bottom: 14px;
  }}
  h1 {{ margin: 0 0 10px; font-size: clamp(2rem, 5vw, 3rem); }}
  p {{ line-height: 1.7; }}
  .sort-list {{
    list-style: none;
    padding: 0;
    margin: 22px 0;
    display: grid;
    gap: 10px;
  }}
  .sort-item {{
    display: grid;
    grid-template-columns: 28px 1fr;
    gap: 14px;
    align-items: center;
    padding: 14px 16px;
    border-radius: 18px;
    background: #fffaf1;
    border: 1px solid var(--line);
    cursor: grab;
  }}
  .sort-item.dragging {{
    opacity: 0.5;
  }}
  .grab {{
    color: #9b6a35;
    font-weight: 700;
    letter-spacing: -0.1em;
  }}
  .actions {{
    display: grid;
    gap: 12px;
  }}
  @media (min-width: 720px) {{
    .actions {{
      grid-template-columns: 1fr 1fr;
    }}
  }}
  button, .back {{
    border: 0;
    border-radius: 18px;
    padding: 15px 18px;
    text-decoration: none;
    text-align: center;
    color: #fff8f0;
    background: linear-gradient(135deg, #ba6313, #8f4305);
    font: 600 1rem/1.1 "Avenir Next", "PingFang SC", sans-serif;
    cursor: pointer;
  }}
  .back {{
    background: linear-gradient(135deg, #8a5a26, #6d4315);
  }}
  .shutdown {{
    border: 0;
    border-radius: 14px;
    padding: 10px 14px;
    color: #fff8f0;
    background: linear-gradient(135deg, #8c2f17, #6a1f0d);
    font: 600 0.92rem/1.1 "Avenir Next", "PingFang SC", sans-serif;
    cursor: pointer;
  }}
</style>
<div class="panel">
  {self._page_actions()}
  <h1>手动调整顺序</h1>
  <p>原始来源：<strong>{html.escape(source_label)}</strong></p>
  <p>下面这些已经先转成 PDF 了。拖动列表调整最终打印顺序，排好后点“确认顺序并生成打印文件”。</p>
  <form method="post" action="/finalize">
    <input type="hidden" name="job_id" value="{html.escape(job_id)}">
    <ul class="sort-list" id="sortList">{items}</ul>
    <div class="actions">
      <button type="submit">确认顺序并生成打印文件</button>
      <a class="back" href="/">重新上传</a>
    </div>
  </form>
</div>
<script>
  const list = document.getElementById("sortList");
  let dragging = null;

  function syncHiddenInputs() {{
    for (const item of list.querySelectorAll(".sort-item")) {{
      const input = item.querySelector('input[name="ordered_file"]');
      input.value = item.dataset.name;
    }}
  }}

  for (const item of list.querySelectorAll(".sort-item")) {{
    item.addEventListener("dragstart", () => {{
      dragging = item;
      item.classList.add("dragging");
    }});
    item.addEventListener("dragend", () => {{
      item.classList.remove("dragging");
      dragging = null;
      syncHiddenInputs();
    }});
  }}

  list.addEventListener("dragover", (event) => {{
    event.preventDefault();
    const after = [...list.querySelectorAll(".sort-item:not(.dragging)")].find((item) => {{
      const rect = item.getBoundingClientRect();
      return event.clientY < rect.top + rect.height / 2;
    }});
    if (!dragging) return;
    if (!after) {{
      list.appendChild(dragging);
    }} else {{
      list.insertBefore(dragging, after);
    }}
  }});
</script>
</html>"""

    def _serve_file(self, parsed) -> None:
        params = parse_qs(parsed.query)
        job_id = params.get("job", [""])[0]
        name = params.get("file", [""])[0]
        mode = params.get("mode", ["inline"])[0]

        if not job_id or not name:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing download parameters")
            return

        allowed_root = (WORK_ROOT / job_id / "output").resolve()
        matches = list(allowed_root.rglob(Path(name).name))
        file_path = next((path.resolve() for path in matches if path.is_file()), None)
        if file_path is None or allowed_root not in file_path.parents:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(data)))
        disposition = "attachment" if mode == "download" else "inline"
        self.send_header(
            "Content-Disposition",
            content_disposition_value(disposition, file_path.name),
        )
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _reveal_in_finder(self, directory: Path) -> None:
        try:
            subprocess.Popen(
                ["/usr/bin/open", str(directory)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def _send_error_page(self, message: str) -> None:
        html = f"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<title>处理失败</title>
<style>
body {{ font-family: 'SF Pro Text', 'PingFang SC', sans-serif; background: #f6f1e8; color: #2f2419; padding: 40px; }}
.card {{ max-width: 720px; margin: 0 auto; background: #fffaf2; border-radius: 24px; padding: 32px; box-shadow: 0 20px 50px rgba(67, 43, 14, 0.12); }}
a {{ color: #8a4b08; }}
</style>
<div class="card">
  <h1>处理失败</h1>
  <p>{message}</p>
  <p><a href="/">返回重新上传</a></p>
</div>
</html>"""
        self._send_html(html, status=HTTPStatus.BAD_REQUEST)

    def _result_page(
        self,
        *,
        job_id: str,
        source_names: list[str],
        converted_names: list[str],
        total_pages: int,
        merged_name: str,
        odd_name: str,
        even_name: str,
    ) -> str:
        output_dir = (WORK_ROOT / job_id / "output").resolve()
        source_label = "、".join(source_names[:4])
        if len(source_names) > 4:
            source_label += f" 等 {len(source_names)} 个文件"
        converted_count = len(converted_names)
        converted_preview = "".join(
            f'<li><a href="/file?job={job_id}&file={name}&mode=inline" target="_blank" rel="noreferrer">{name}</a></li>'
            for name in converted_names[:8]
        )
        if converted_count > 8:
            converted_preview += f"<li>以及另外 {converted_count - 8} 个转换后的 PDF</li>"
        return f"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>处理完成</title>
<style>
  :root {{
    --bg: #f4ecdd;
    --ink: #2b2117;
    --accent: #a14d00;
    --panel: rgba(255, 251, 244, 0.9);
    --line: rgba(87, 54, 22, 0.12);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    min-height: 100vh;
    background:
      radial-gradient(circle at top right, rgba(255, 214, 153, 0.5), transparent 32%),
      linear-gradient(160deg, #efe5d3 0%, #f8f2e8 46%, #eadbc1 100%);
    color: var(--ink);
    font-family: 'Iowan Old Style', 'Palatino Linotype', 'PingFang SC', serif;
    display: grid;
    place-items: center;
    padding: 28px;
  }}
  .panel {{
    width: min(760px, 100%);
    background: var(--panel);
    backdrop-filter: blur(12px);
    border: 1px solid var(--line);
    border-radius: 28px;
    padding: 34px;
    box-shadow: 0 24px 60px rgba(76, 49, 21, 0.14);
  }}
  .top-actions {{
    display: flex;
    justify-content: flex-end;
    margin-bottom: 14px;
  }}
  h1 {{ margin: 0 0 12px; font-size: clamp(2rem, 5vw, 3.2rem); }}
  p {{ line-height: 1.7; }}
  .downloads {{
    display: grid;
    gap: 14px;
    margin: 26px 0;
  }}
  .summary {{
    padding: 16px 18px;
    border-radius: 18px;
    background: rgba(255, 250, 241, 0.72);
    border: 1px solid var(--line);
  }}
  .files {{
    margin: 12px 0 0;
    padding-left: 1.2rem;
    line-height: 1.8;
  }}
  .files a {{
    color: var(--accent);
  }}
  .download {{
    display: block;
    text-decoration: none;
    color: inherit;
    background: #fffaf1;
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 18px 20px;
  }}
  .download strong {{
    display: block;
    margin-bottom: 6px;
    color: var(--accent);
  }}
  .download-row {{
    display: grid;
    gap: 12px;
  }}
  @media (min-width: 640px) {{
    .download-row {{
      grid-template-columns: 1fr 1fr;
    }}
  }}
  .secondary {{
    display: block;
    text-decoration: none;
    color: var(--accent);
    padding: 14px 16px;
    border-radius: 18px;
    background: rgba(255, 250, 241, 0.8);
    border: 1px solid var(--line);
  }}
  code {{
    display: block;
    margin-top: 18px;
    padding: 14px 16px;
    border-radius: 16px;
    background: rgba(72, 47, 18, 0.06);
    color: #5e3911;
    overflow-wrap: anywhere;
  }}
  ol {{
    padding-left: 1.2rem;
    line-height: 1.8;
  }}
  .back {{
    display: inline-block;
    margin-top: 20px;
    color: var(--accent);
  }}
  .shutdown {{
    border: 0;
    border-radius: 14px;
    padding: 10px 14px;
    color: #fff8f0;
    background: linear-gradient(135deg, #8c2f17, #6a1f0d);
    font: 600 0.92rem/1.1 "Avenir Next", "PingFang SC", sans-serif;
    cursor: pointer;
  }}
</style>
<div class="panel">
  {self._page_actions()}
  <h1>准备好了</h1>
  <p>源文件：<strong>{source_label}</strong></p>
  <div class="downloads">
    <div class="summary">
      <strong>已先合并成一个总文件</strong>
      <p>总页数：{total_pages} 页。这里只做按顺序并接，不会把两个文件印到同一张纸上；如果前一个文件是奇数页，会自动补空白背页，让下一个文件从新纸正面开始。</p>
      <p>本次一共转换了 {converted_count} 个 PDF。</p>
      <a class="download" href="/file?job={job_id}&file={merged_name}&mode=inline" target="_blank" rel="noreferrer">
        <strong>打开合并后的总 PDF</strong>
        <span>{merged_name}</span>
      </a>
      <ul class="files">
        {converted_preview}
      </ul>
    </div>
    <div class="download-row">
      <a class="download" href="/file?job={job_id}&file={odd_name}&mode=inline" target="_blank" rel="noreferrer">
        <strong>打开第一次打印 PDF</strong>
        <span>{odd_name}</span>
      </a>
      <a class="secondary" href="/file?job={job_id}&file={odd_name}&mode=download">
        下载第一次打印 PDF
      </a>
    </div>
    <div class="download-row">
      <a class="download" href="/file?job={job_id}&file={even_name}&mode=inline" target="_blank" rel="noreferrer">
        <strong>打开第二次打印 PDF</strong>
        <span>{even_name}</span>
      </a>
      <a class="secondary" href="/file?job={job_id}&file={even_name}&mode=download">
        下载第二次打印 PDF
      </a>
    </div>
  </div>
  <ol>
    <li>先点“打开第一次打印 PDF”，在新标签页里直接打印。</li>
    <li>打印完成后，请按你这台打印机的实际进纸方向决定是否需要调头或翻面回纸。</li>
    <li>再点“打开第二次打印 PDF”，在新标签页里直接打印；这份 PDF 默认不翻转，且已自动倒序，并会在需要时自动补充空白页。</li>
  </ol>
  <p>如果浏览器下载仍然不稳定，文件已经保存在这里：</p>
  <code>{output_dir}</code>
  <a class="back" href="/">继续处理下一份 PDF</a>
</div>
</html>"""


def main() -> int:
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    host = "127.0.0.1"
    port = 8765
    server = ThreadingHTTPServer((host, port), ManualDuplexHandler)
    print(f"Manual duplex web app running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
