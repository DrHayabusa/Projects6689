import csv
import os
import sqlite3

import xlsxwriter

from parser import get_csv_encoding


SHEET_COLUMNS = [
    ("IP Address", 17),
    ("DNS Name", 24),
    ("Vulnerability Name", 34),
    ("CVE", 20),
    ("Severity", 12),
    ("Exploit?", 10),
    ("Patch Priority", 14),
    ("Asset Exposure (on 1000)", 20),
    ("Vulnerability Finding", 40),
    ("Summary", 34),
    ("Description", 48),
    ("Remediation", 44),
    ("KB Links", 30),
    ("Platform Details", 30),
    ("First Discovered", 18),
    ("Last Observed", 18),
]


ROW_STYLE_PROPS = {
    "critical": {
        "bg_color": "#FDECEC",
        "border": 1,
        "border_color": "#F1C9C9",
        "text_wrap": True,
        "valign": "top",
    },
    "high": {
        "bg_color": "#FFF3E8",
        "border": 1,
        "border_color": "#F7D0B2",
        "text_wrap": True,
        "valign": "top",
    },
    "medium": {
        "bg_color": "#FFFBEA",
        "border": 1,
        "border_color": "#F3E0A6",
        "text_wrap": True,
        "valign": "top",
    },
    "low": {
        "bg_color": "#EEF9F2",
        "border": 1,
        "border_color": "#CAE8D0",
        "text_wrap": True,
        "valign": "top",
    },
    "info": {
        "bg_color": "#F5F7FA",
        "border": 1,
        "border_color": "#DDE3EA",
        "text_wrap": True,
        "valign": "top",
    },
}


SEVERITY_FONT_PROPS = {
    "severity_critical": {"font_color": "#B42318", "bold": True},
    "severity_high": {"font_color": "#C2410C", "bold": True},
    "severity_medium": {"font_color": "#9A6700", "bold": True},
    "severity_low": {"font_color": "#027A48", "bold": True},
    "severity_info": {"font_color": "#475467", "bold": True},
}


EXPOSURE_FONT_PROPS = {
    "exposure_hot": {"font_color": "#B42318", "bold": True},
    "exposure_warm": {"font_color": "#C2410C", "bold": True},
    "exposure_normal": {"font_color": "#0F172A"},
}


def build_excel_report(csv_path, db_path, output_path, group_summaries, progress_callback=None):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    workbook = xlsxwriter.Workbook(
        output_path,
        {
            "constant_memory": True,
            "strings_to_urls": False,
        },
    )
    formats = build_formats(workbook)
    write_raw_sheet(workbook, formats, csv_path, progress_callback)
    write_analyzed_sheet(workbook, formats, db_path, group_summaries, progress_callback)
    workbook.close()


def build_formats(workbook):
    formats = {
        "raw_header": workbook.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#184E3A",
                "border": 1,
                "border_color": "#D7E2DD",
                "valign": "top",
            }
        ),
        "raw_cell": workbook.add_format(
            {
                "text_wrap": True,
                "valign": "top",
                "border": 1,
                "border_color": "#E3EBE7",
            }
        ),
        "sheet_header": workbook.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#184E3A",
                "border": 1,
                "border_color": "#184E3A",
                "valign": "vcenter",
            }
        ),
        "group_header": workbook.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#0F3D2E",
                "border": 1,
                "border_color": "#0F3D2E",
                "font_size": 12,
                "valign": "vcenter",
            }
        ),
        "priority_p1": workbook.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#B42318",
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "border_color": "#B42318",
            }
        ),
        "priority_p2": workbook.add_format(
            {
                "bold": True,
                "font_color": "#7A2E0B",
                "bg_color": "#F79009",
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "border_color": "#F79009",
            }
        ),
        "priority_p3": workbook.add_format(
            {
                "bold": True,
                "font_color": "#4E3A00",
                "bg_color": "#FACC15",
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "border_color": "#FACC15",
            }
        ),
        "priority_p4": workbook.add_format(
            {
                "bold": True,
                "font_color": "#0F5132",
                "bg_color": "#22C55E",
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "border_color": "#22C55E",
            }
        ),
    }

    for row_key, properties in ROW_STYLE_PROPS.items():
        formats[f"{row_key}_row"] = workbook.add_format(properties)
        for severity_key, severity_props in SEVERITY_FONT_PROPS.items():
            merged = dict(properties)
            merged.update(severity_props)
            formats[f"{row_key}_{severity_key}"] = workbook.add_format(merged)
        for exposure_key, exposure_props in EXPOSURE_FONT_PROPS.items():
            merged = dict(properties)
            merged.update(exposure_props)
            formats[f"{row_key}_{exposure_key}"] = workbook.add_format(merged)

    return formats


def write_raw_sheet(workbook, formats, csv_path, progress_callback=None):
    sheet = workbook.add_worksheet("Raw Data")
    sheet.set_tab_color("#1D6F42")
    encoding = get_csv_encoding(csv_path)

    with open(csv_path, "r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle)
        for row_idx, row in enumerate(reader):
            row_format = formats["raw_header"] if row_idx == 0 else formats["raw_cell"]
            for col_idx, value in enumerate(row):
                sheet.write(row_idx, col_idx, value, row_format)
            if progress_callback and row_idx and row_idx % 1000 == 0:
                progress_callback(
                    min(70, 58 + (row_idx // 1000)),
                    f"Writing raw data row {row_idx:,}",
                )

    sheet.freeze_panes(1, 0)


def write_analyzed_sheet(workbook, formats, db_path, group_summaries, progress_callback=None):
    sheet = workbook.add_worksheet("Analysed")
    sheet.set_tab_color("#1D6F42")
    sheet.freeze_panes(1, 0)

    for col_idx, (label, width) in enumerate(SHEET_COLUMNS):
        sheet.set_column(col_idx, col_idx, width)
        sheet.write(0, col_idx, label, formats["sheet_header"])

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    row_idx = 1
    total_groups = max(len(group_summaries), 1)

    for group_index, group in enumerate(group_summaries, start=1):
        summary_text = build_group_summary(group)
        sheet.merge_range(row_idx, 0, row_idx, len(SHEET_COLUMNS) - 1, summary_text, formats["group_header"])
        row_idx += 1

        query = """
            SELECT *
            FROM findings
            WHERE ip_address = ?
            ORDER BY
                patch_priority_rank ASC,
                severity_rank DESC,
                exposure_score DESC,
                vuln_name ASC
        """
        for finding in connection.execute(query, (group["ip_address"],)):
            row_key = choose_row_key(finding["severity"])
            row_format = formats[f"{row_key}_row"]
            values = [
                finding["ip_address"],
                finding["dns_name"],
                finding["vuln_name"],
                finding["cve"],
                finding["severity"],
                finding["exploit_display"],
                finding["patch_priority"],
                finding["exposure_score"],
                finding["finding"],
                finding["summary"],
                finding["description"],
                finding["remediation"],
                finding["kb_links"],
                finding["platform_details"],
                finding["first_discovered"],
                finding["last_observed"],
            ]
            for col_idx, value in enumerate(values):
                write_cell(sheet, row_idx, col_idx, value, row_key, row_format, formats)
            row_idx += 1

        if progress_callback:
            completed = int((group_index / total_groups) * 28)
            progress_callback(70 + completed, f"Formatting host group {group_index:,} of {total_groups:,}")

    sheet.autofilter(0, 0, max(row_idx - 1, 0), len(SHEET_COLUMNS) - 1)
    connection.close()


def build_group_summary(group):
    counts = []
    if group["critical_count"]:
        counts.append(f"{group['critical_count']} Critical")
    if group["high_count"]:
        counts.append(f"{group['high_count']} High")
    if group["medium_count"]:
        counts.append(f"{group['medium_count']} Medium")
    if group["low_count"]:
        counts.append(f"{group['low_count']} Low")
    if group["info_count"] and not counts:
        counts.append(f"{group['info_count']} Info")
    severity_summary = " | ".join(counts) if counts else "0 Findings"
    dns_text = f" ({group['dns_name']})" if group["dns_name"] else ""
    return (
        f"{group['ip_address']}{dns_text}     "
        f"{severity_summary}     "
        f"Total: {group['total_findings']}     "
        f"Immediate Patch Needed: {group['p1_count']}"
    )


def choose_row_key(severity):
    return {
        "Critical": "critical",
        "High": "high",
        "Medium": "medium",
        "Low": "low",
        "Info": "info",
    }.get(severity, "info")


def choose_severity_format_key(severity):
    return {
        "Critical": "severity_critical",
        "High": "severity_high",
        "Medium": "severity_medium",
        "Low": "severity_low",
        "Info": "severity_info",
    }.get(severity, "severity_info")


def write_cell(sheet, row_idx, col_idx, value, row_key, base_format, formats):
    if col_idx == 4:
        severity_format = formats[f"{row_key}_{choose_severity_format_key(value)}"]
        sheet.write(row_idx, col_idx, value, severity_format)
        return
    if col_idx == 6:
        priority_format = formats.get(f"priority_{str(value).lower()}", base_format)
        sheet.write(row_idx, col_idx, value, priority_format)
        return
    if col_idx == 7:
        exposure = int(value or 0)
        if exposure >= 850:
            exposure_format = formats[f"{row_key}_exposure_hot"]
        elif exposure >= 650:
            exposure_format = formats[f"{row_key}_exposure_warm"]
        else:
            exposure_format = formats[f"{row_key}_exposure_normal"]
        sheet.write(row_idx, col_idx, exposure, exposure_format)
        return
    sheet.write(row_idx, col_idx, value, base_format)
