"""
TikTok Farm UI - NiceGUI
Left panel: controls
Right panel: logs
"""

import threading
import time
from datetime import datetime
from typing import Optional

from nicegui import ui

import tiktok_farm


class LogHandler:
    def __init__(self):
        self.logs = []

    def add(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
        }
        self.logs.append(entry)
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]
        print(f"[{timestamp}] [{level}] {message}")
        return entry

    def clear(self):
        self.logs = []

    def info(self, message: str):
        self.add(message, "INFO")

    def warning(self, message: str):
        self.add(message, "WARNING")

    def error(self, message: str):
        self.add(message, "ERROR")

    def success(self, message: str):
        self.add(f"{message}", "SUCCESS")

    def tap(self, message: str):
        self.add(message, "TAP")


log_handler = LogHandler()
is_running = False
stop_requested = False


def set_status(label, status: str):
    if status == "running":
        label.set_content('<span class="status-badge status-running">Running</span>')
    else:
        label.set_content('<span class="status-badge status-ready">Ready</span>')


def run_flow(
    manual: bool,
    manual_line: str,
    custom_link: str,
    status_label,
    start_btn,
):
    global is_running, stop_requested
    try:
        tiktok_farm.log = log_handler
        tiktok_farm.clear_stop()
        set_status(status_label, "running")
        start_btn.props("disable")
        is_running = True
        stop_requested = False

        device_key = tiktok_farm.Config.DEFAULT_DEVICE_KEY
        pchanger = tiktok_farm.PchangerAPI()
        log_handler.info("Getting device serial from Pchanger...")
        device_serial = tiktok_farm.get_device_serial_from_key(pchanger, device_key)
        if not device_serial:
            log_handler.error("Cannot get device serial from Pchanger!")
            return
        log_handler.success(f"Device Serial: {device_serial}")

        if not pchanger.wait_for_device_ready(device_key):
            log_handler.error("Device not ready, exiting...")
            return
        if stop_requested:
            log_handler.warning("Stop requested before running flow.")
            return

        if manual:
            parsed = tiktok_farm._parse_user_pass_mail(manual_line)
            if not parsed:
                log_handler.error("Invalid format. Example: user|pass|mail")
                return
            username, password, email, refresh_token, client_id = parsed
            log_handler.info(f"Processing manual: {username}")
            automation = tiktok_farm.TikTokAutomation(device_serial)
            automation.run_full_flow(
                username=username,
                password=password,
                email=email,
                refresh_token=refresh_token,
                client_id=client_id,
                custom_link=custom_link or None,
            )
            return

        # Google Sheets flow
        sheet_url = tiktok_farm.Config.SHEET_URL
        if not sheet_url:
            log_handler.error("Google Sheet URL is empty")
            return
        try:
            sheets = tiktok_farm.GoogleSheetsHandler(
                tiktok_farm.Config.CREDENTIALS_FILE, sheet_url
            )
        except Exception as e:
            log_handler.error(f"Cannot connect to Google Sheets: {e}")
            return

        row_data = sheets.get_next_unprocessed_row_skip_status()
        if not row_data:
            log_handler.info("No more data to process")
            return
        if stop_requested:
            log_handler.warning("Stop requested before running flow.")
            return

        row_num, username, password, mail_data = row_data
        mail_parts = mail_data.split("|")
        email = mail_parts[0] if len(mail_parts) > 0 else ""
        refresh_token = mail_parts[2] if len(mail_parts) > 2 else ""
        client_id = mail_parts[3] if len(mail_parts) > 3 else ""

        log_handler.info(f"Processing: {username}")
        log_handler.info(f"Email: {email}")
        log_handler.info(
            f"Token: {refresh_token[:20]}..." if refresh_token else "Token: (empty)"
        )

        sheets.update_status(row_num, "PROCESSING")

        try:
            automation = tiktok_farm.TikTokAutomation(device_serial)
            device_model = automation.get_device_model()
            sheets.update_device_id(row_num, device_model)
            log_handler.info(f"Device Model: {device_model}")
        except Exception as e:
            log_handler.error(f"Cannot connect to device: {e}")
            sheets.update_status(row_num, f"ERROR: {e}")
            return

        success = automation.run_full_flow(
            username=username,
            password=password,
            email=email,
            refresh_token=refresh_token,
            client_id=client_id,
            custom_link=None,
        )
        if success:
            sheets.update_status(row_num, "SUCCESS (no backup)")
        else:
            sheets.update_status(row_num, "FAILED")
    except tiktok_farm.StopRequested:
        log_handler.warning("Stopped immediately by user.")
    except Exception as e:
        log_handler.error(f"UI flow error: {e}")
    finally:
        is_running = False
        stop_requested = False
        set_status(status_label, "ready")
        start_btn.props(remove="disable")


def open_deeplink_only(link: str, status_label):
    link = (link or "").strip()
    if not link:
        log_handler.warning("Empty link.")
        return
    device_key = tiktok_farm.Config.DEFAULT_DEVICE_KEY
    pchanger = tiktok_farm.PchangerAPI()
    log_handler.info("Getting device serial from Pchanger...")
    device_serial = tiktok_farm.get_device_serial_from_key(pchanger, device_key)
    if not device_serial:
        log_handler.error("Cannot get device serial from Pchanger!")
        return
    if not pchanger.wait_for_device_ready(device_key):
        log_handler.error("Device not ready, cannot open link.")
        return
    set_status(status_label, "running")
    try:
        automation = tiktok_farm.TikTokAutomation(device_serial)
        log_handler.info(f"Opening link: {link}")
        automation.open_url(link)
    finally:
        set_status(status_label, "ready")


def update_logs(container, count_label):
    if not log_handler.logs:
        container.set_content('<div class="log-empty">No logs yet</div>')
        count_label.set_text("0 entries")
        return
    html = []
    for entry in log_handler.logs:
        level = entry["level"]
        html.append(
            f'<div class="log-entry">'
            f'<span class="log-time">{entry["timestamp"]}</span>'
            f'<span class="log-level log-{level}">{level}</span>'
            f'{entry["message"]}'
            f'</div>'
        )
    container.set_content("".join(html))
    count_label.set_text(f"{len(log_handler.logs)} entries")


def create_ui():
    ui.add_head_html(
        """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body {
            width: 100% !important;
            height: 100vh !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
        }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
        }
        .nicegui-content, .q-page, .q-layout, .q-page-container {
            width: 100% !important;
            max-width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        .app-container {
            width: 100% !important;
            height: 100vh;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(148, 163, 184, 0.2);
        }
        .header h1 {
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(90deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .status-badge {
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-ready { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
        .status-running { background: rgba(59, 130, 246, 0.15); color: #60a5fa; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: row;
            gap: 20px;
            min-height: 0;
            width: 100%;
        }
        .left-panel {
            width: 65%;
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
            gap: 12px;
            overflow-y: auto;
        }
        .right-panel {
            width: 35%;
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
            min-height: 0;
        }
        .card {
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(148, 163, 184, 0.15);
            border-radius: 12px;
            padding: 16px;
        }
        .card-title {
            font-size: 14px;
            font-weight: 600;
            color: #f1f5f9;
            margin-bottom: 4px;
        }
        .card-hint {
            font-size: 12px;
            color: #94a3b8;
            margin-bottom: 12px;
        }
        .input-field textarea,
        .input-field input {
            width: 100%;
            background: rgba(15, 23, 42, 0.6) !important;
            border: 1px solid rgba(148, 163, 184, 0.2) !important;
            border-radius: 8px !important;
            color: #e2e8f0 !important;
            font-family: 'Consolas', monospace !important;
            font-size: 13px !important;
            padding: 10px 12px !important;
        }
        .btn-row {
            display: flex;
            gap: 10px;
            margin-top: 4px;
        }
        .btn-row.tight {
            gap: 8px;
        }
        .link-input {
            flex: 1;
            min-width: 0;
        }
       .btn-open {
            flex: 0 0 auto;
            padding: 6px 10px !important;
            font-size: 11px !important;
            white-space: nowrap;
            line-height: 1.1;
        }
        .btn {
            flex: 1;
            padding: 12px 20px !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            cursor: pointer;
            text-transform: none !important;
        }
        .btn-start {
            background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
            color: white !important;
        }
        .btn-clear {
            background: transparent !important;
            border: 1px solid rgba(148, 163, 184, 0.3) !important;
            color: #94a3b8 !important;
            padding: 6px 12px !important;
            font-size: 12px !important;
        }
        .log-card {
            flex: 1;
            display: flex;
            flex-direction: column;
            min-height: 0;
        }
        .log-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        .log-container {
            flex: 1;
            background: #0f172a;
            border-radius: 8px;
            padding: 12px;
            font-family: 'Consolas', monospace;
            font-size: 12px;
            overflow-y: auto;
            min-height: 0;
        }
        .log-entry {
            padding: 4px 0;
            border-bottom: 1px solid rgba(148, 163, 184, 0.1);
        }
        .log-time { color: #64748b; margin-right: 8px; }
        .log-level {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
            margin-right: 8px;
        }
        .log-INFO { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
        .log-SUCCESS { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
        .log-WARNING { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
        .log-ERROR { background: rgba(239, 68, 68, 0.2); color: #f87171; }
        .log-TAP { background: rgba(14, 165, 233, 0.2); color: #38bdf8; }
        .log-empty {
            color: #64748b;
            text-align: center;
            padding: 40px;
        }
        .log-count { color: #64748b; font-size: 12px; }
        .q-checkbox__label { color: #e2e8f0 !important; font-weight: 500; }
    </style>
        """
    )

    with ui.element("div").classes("app-container"):
        with ui.element("div").classes("main-content"):
            with ui.element("div").classes("left-panel"):
                with ui.element("div").classes("card"):
                    ui.html('<div class="card-title">Mode</div>', sanitize=False)
                    ui.html(
                        '<div class="card-hint">Manual: user|pass|mail. Sheet: skip status 1 or PROCESSING.</div>',
                        sanitize=False,
                    )
                    manual_checkbox = ui.checkbox("Use manual account")
                    manual_input = ui.textarea(
                        placeholder="user|pass|mail"
                    ).classes("input-field").props("outlined rows=3")

                    def toggle_inputs():
                        manual_input.set_visibility(manual_checkbox.value)

                    manual_checkbox.on(
                        "update:model-value", lambda _: toggle_inputs()
                    )
                    toggle_inputs()

                with ui.element("div").classes("card"):
                    ui.html('<div class="card-title">Open Link</div>', sanitize=False)
                    with ui.element("div").classes("btn-row tight"):
                        link_input = ui.input(
                            placeholder="https://vt.tiktok.com/..."
                        ).classes("input-field link-input").props("outlined")
                        open_btn = ui.button("Open").classes("btn btn-start btn-open")

                with ui.element("div").classes("btn-row"):
                    start_btn = ui.button("Start").classes("btn btn-start")
                    stop_btn = ui.button("Stop").classes("btn btn-clear")
                    status_label = ui.html("", sanitize=False)

            with ui.element("div").classes("right-panel"):
                with ui.element("div").classes("card log-card"):
                    with ui.element("div").classes("log-header"):
                        ui.html(
                            '<div class="card-title">Log Output</div>',
                            sanitize=False,
                        )
                        with ui.row().classes("items-center gap-2"):
                            log_count = ui.label("0 entries").classes("log-count")
                            ui.button(
                                "Clear",
                                on_click=lambda: log_handler.clear(),
                            ).classes("btn btn-clear")
                    log_container = ui.html("", sanitize=False).classes("log-container")
                    ui.timer(0.5, lambda: update_logs(log_container, log_count))

        def on_start():
            if is_running:
                return
            manual = manual_checkbox.value
            line = manual_input.value or ""
            custom_link = (link_input.value or "").strip() if manual else ""
            threading.Thread(
                target=run_flow,
                args=(manual, line, custom_link, status_label, start_btn),
                daemon=True,
            ).start()

        start_btn.on("click", lambda: on_start())
        stop_btn.on("click", lambda: request_stop(status_label))
        open_btn.on("click", lambda: open_deeplink_only(link_input.value, status_label))


def request_stop(status_label):
    global stop_requested
    stop_requested = True
    tiktok_farm.request_stop()
    log_handler.warning("Stop requested. Stopping immediately.")
    if not is_running:
        set_status(status_label, "ready")


@ui.page("/")
def main_page():
    create_ui()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="TikTok Farm UI", port=8081)
