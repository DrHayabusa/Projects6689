import csv
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone


csv.field_size_limit(min(2147483647, 10**9))


OUTPUT_COLUMNS = [
    "IP Address",
    "DNS Name",
    "Vulnerability Name",
    "CVE",
    "Severity",
    "Exploit?",
    "Patch Priority",
    "Asset Exposure (on 1000)",
    "Vulnerability Finding",
    "Summary",
    "Description",
    "Remediation",
    "KB Links",
    "Platform Details",
    "First Discovered",
    "Last Observed",
]


DB_COLUMNS = [
    "ip_address",
    "dns_name",
    "vuln_name",
    "cve",
    "severity",
    "severity_rank",
    "exploit_display",
    "exploit_flag",
    "patch_priority",
    "patch_priority_rank",
    "exposure_score",
    "finding",
    "summary",
    "description",
    "remediation",
    "kb_links",
    "platform_details",
    "first_discovered",
    "last_observed",
    "port",
    "protocol",
    "plugin_id",
    "cvss_score",
]


SC_FIELD_MARKERS = {
    "vulnerabilitypriorityrating",
    "exploitpredictionscoringsystemepss",
    "riskfactor",
    "pluginoutput",
    "steps to remediate",
    "recastriskcomment",
    "acceptriskcomment",
}


IO_FIELD_MARKERS = {
    "ageindays",
    "asset.displayfqdn",
    "definition.exploitabilityease",
    "definition.vpr.score",
    "definition.vprv2.score",
    "vulnage",
    "vulnsladate",
}


FIELD_ALIASES = {
    "ip_address": [
        "IP Address",
        "Host",
        "Asset",
        "asset.display_ipv4_address",
        "asset.display_ipv6_address",
        "asset.ipv4_addresses",
        "asset.ipv6_addresses",
        "asset.name",
    ],
    "dns_name": [
        "DNS Name",
        "asset.display_fqdn",
        "asset.host_name",
        "asset.name",
        "asset.netbios_name",
        "NetBIOS Name",
    ],
    "vuln_name": [
        "Plugin Name",
        "Vulnerability Name",
        "Name",
        "definition.name",
    ],
    "cve": [
        "CVE",
        "definition.cve",
    ],
    "severity": [
        "Severity",
        "Risk Factor",
        "Risk",
        "definition.severity",
    ],
    "exploit_sc": [
        "Exploit?",
    ],
    "exploit_io": [
        "definition.exploitability_ease",
    ],
    "exploit_frameworks": [
        "Exploit Frameworks",
        "definition.exploited_by_nessus",
        "definition.exploited_by_malware",
    ],
    "finding": [
        "Plugin Output",
        "output",
    ],
    "summary": [
        "Synopsis",
        "definition.synopsis",
    ],
    "description": [
        "Description",
        "definition.description",
    ],
    "remediation": [
        "Steps to Remediate",
        "Solution",
        "definition.solution",
        "definition.workaround",
    ],
    "kb_links": [
        "See Also",
        "Cross References",
        "definition.see_also",
        "definition.references",
    ],
    "first_discovered": [
        "First Discovered",
        "First Detected",
        "First Seen",
        "first_observed",
    ],
    "last_observed": [
        "Last Observed",
        "Last Seen",
        "Last Detected",
        "last_seen",
    ],
    "port": [
        "Port",
        "port",
    ],
    "protocol": [
        "Protocol",
        "protocol",
    ],
    "plugin_id": [
        "Plugin",
        "Plugin ID",
        "Plugin Id",
        "definition.id",
    ],
    "cvss4": [
        "CVSS V4 Base Score",
        "definition.cvss4.base_score",
    ],
    "cvss3": [
        "CVSS V3 Base Score",
        "CVSSv3 Base Score",
        "CVSS Base Score",
        "CVSS Score",
        "definition.cvss3.base_score",
    ],
    "cvss2": [
        "CVSS V2 Base Score",
        "definition.cvss2.base_score",
    ],
    "vpr": [
        "Vulnerability Priority Rating",
        "definition.vpr.score",
        "definition.vpr_v2.score",
    ],
    "epss": [
        "Exploit Prediction Scoring System (EPSS)",
        "definition.epss.score",
    ],
    "os": [
        "asset.operating_system",
        "asset.operating_systems",
    ],
    "system_type": [
        "asset.system_type",
    ],
    "repository": [
        "Repository",
        "asset.network.name",
        "asset.network.id",
    ],
    "plugin_published": [
        "Plugin Publication Date",
        "definition.plugin_published",
    ],
    "patch_published": [
        "Patch Publication Date",
        "definition.patch_published",
    ],
    "vuln_published": [
        "Vuln Publication Date",
        "definition.vulnerability_published",
    ],
    "age_days": [
        "age_in_days",
        "vuln_age",
    ],
}


SEVERITY_MAP = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "moderate": 2,
    "low": 1,
    "info": 0,
    "informational": 0,
    "none": 0,
}


PRIORITY_MATRIX = {
    (True, "Critical"): ("P1", 1),
    (True, "High"): ("P1", 1),
    (True, "Medium"): ("P2", 2),
    (True, "Low"): ("P2", 2),
    (True, "Info"): ("P3", 3),
    (False, "Critical"): ("P2", 2),
    (False, "High"): ("P2", 2),
    (False, "Medium"): ("P3", 3),
    (False, "Low"): ("P4", 4),
    (False, "Info"): ("P4", 4),
}


def normalize_header(value):
    if value is None:
        return ""
    lowered = value.strip().lower().replace("\ufeff", "")
    lowered = lowered.replace("/", " ")
    lowered = lowered.replace("_", " ")
    lowered = lowered.replace("-", " ")
    lowered = re.sub(r"[^a-z0-9. ]+", "", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered.replace(" ", "")


def build_header_index(headers):
    return {normalize_header(header): header for header in headers if header}


def pick_value(row, header_index, aliases):
    for alias in aliases:
        header = header_index.get(normalize_header(alias))
        if not header:
            continue
        value = clean_text(row.get(header, ""))
        if value:
            return value
    return ""


def pick_values(row, header_index, aliases):
    values = []
    for alias in aliases:
        header = header_index.get(normalize_header(alias))
        if not header:
            continue
        value = clean_text(row.get(header, ""))
        if value:
            values.append(value)
    return values


def clean_text(value):
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").strip()
    return re.sub(r"\s+\n", "\n", text)


def split_multi_value(value):
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,;\n]+", value) if item.strip()]


def choose_ip(raw_value):
    values = split_multi_value(raw_value)
    return values[0] if values else raw_value


def choose_dns(raw_value):
    values = split_multi_value(raw_value)
    return values[0] if values else raw_value


def detect_source(headers):
    normalized = {normalize_header(header) for header in headers}
    if normalized & {normalize_header(marker) for marker in IO_FIELD_MARKERS}:
        return "io"
    if normalized & {normalize_header(marker) for marker in SC_FIELD_MARKERS}:
        return "sc"
    return "generic"


def normalize_severity(value):
    cleaned = clean_text(value)
    if not cleaned:
        return "Unknown", -1
    if cleaned.isdigit():
        numeric = int(cleaned)
        numeric_map = {
            4: "Critical",
            3: "High",
            2: "Medium",
            1: "Low",
            0: "Info",
        }
        label = numeric_map.get(numeric, "Unknown")
        return label, SEVERITY_MAP.get(label.lower(), -1)
    lowered = cleaned.lower()
    for label, rank in SEVERITY_MAP.items():
        if label in lowered:
            normalized = "Medium" if label == "moderate" else label.title()
            normalized = "Info" if normalized == "Informational" else normalized
            return normalized, rank
    return cleaned.title(), -1


def parse_float(value):
    cleaned = clean_text(value)
    if not cleaned:
        return None
    simplified = cleaned.replace("%", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", simplified)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def first_number(*values):
    for value in values:
        parsed = parse_float(value)
        if parsed is not None:
            return parsed
    return None


def normalize_probability(value):
    if value is None:
        return None
    if value > 1:
        if value <= 100:
            return value / 100.0
        return 1.0
    if value < 0:
        return 0.0
    return value


def normalize_ten_point_score(value):
    if value is None:
        return None
    if value > 10:
        if value <= 100:
            return value / 10.0
        return 10.0
    if value < 0:
        return 0.0
    return value


def exploit_from_sc(value):
    lowered = clean_text(value).lower()
    if not lowered:
        return False
    return lowered in {"yes", "true", "1", "y"} or "yes" in lowered


def exploit_from_io(value):
    lowered = clean_text(value).lower()
    if not lowered:
        return False
    positive_markers = [
        "available",
        "functional",
        "public exploit",
        "weaponized",
        "exploited",
        "easy",
        "high",
        "proof of concept",
    ]
    negative_markers = [
        "no known",
        "unproven",
        "difficult",
        "not available",
        "no exploit",
    ]
    if any(marker in lowered for marker in negative_markers):
        return False
    return any(marker in lowered for marker in positive_markers)


def fallback_exploit_signal(value):
    lowered = clean_text(value).lower()
    if not lowered:
        return False
    return lowered in {"true", "yes", "1"} or any(
        marker in lowered for marker in ["metasploit", "canvas", "core impact", "available", "exploit"]
    )


def build_platform_details(os_value, system_type, repository, protocol, port):
    parts = []
    if os_value:
        parts.append(os_value)
    if system_type:
        parts.append(system_type)
    if protocol or port:
        endpoint = "/".join([item for item in [protocol.upper() if protocol else "", port] if item])
        if endpoint:
            parts.append(endpoint)
    if repository:
        parts.append(repository)
    return " | ".join(parts)


def summarize_text(text, fallback=""):
    cleaned = clean_text(text)
    if cleaned:
        first_sentence = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)[0]
        return first_sentence[:240]
    return fallback


def build_finding(plugin_output, protocol, port, plugin_id):
    evidence = clean_text(plugin_output)
    parts = []
    if protocol or port:
        endpoint = "/".join([item for item in [protocol.upper() if protocol else "", port] if item])
        if endpoint:
            parts.append(endpoint)
    if plugin_id:
        parts.append(f"Plugin {plugin_id}")
    if evidence:
        parts.append(evidence)
    return " | ".join(parts)


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def age_bonus(age_days):
    if age_days is None:
        return 0
    if age_days >= 365:
        return 90
    if age_days >= 180:
        return 65
    if age_days >= 90:
        return 40
    if age_days >= 30:
        return 20
    return 0


def freshness_bonus(*date_values):
    recent_bonus = 0
    now = datetime.now(timezone.utc)
    for date_value in date_values:
        parsed = parse_date(date_value)
        if not parsed:
            continue
        age = (now - parsed).days
        if age <= 30:
            recent_bonus = max(recent_bonus, 40)
        elif age <= 90:
            recent_bonus = max(recent_bonus, 20)
    return recent_bonus


def parse_date(value):
    cleaned = clean_text(value)
    if not cleaned:
        return None
    candidates = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    trimmed = cleaned.split(".")[0] if "T" in cleaned and "." in cleaned else cleaned
    for candidate in candidates:
        try:
            parsed = datetime.strptime(trimmed, candidate)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def compute_exposure_score(severity_rank, exploit_flag, cvss_score, vpr_score, epss_score, age_days, recency_bonus):
    cvss_score = normalize_ten_point_score(cvss_score)
    vpr_score = normalize_ten_point_score(vpr_score)
    epss_score = normalize_probability(epss_score)
    severity_base = {
        4: 380,
        3: 290,
        2: 190,
        1: 110,
        0: 40,
        -1: 25,
    }.get(severity_rank, 25)
    exploit_bonus = 150 if exploit_flag else 0
    cvss_component = ((cvss_score or 0) / 10.0) * 220
    vpr_component = ((vpr_score or 0) / 10.0) * 170
    epss_component = (epss_score or 0) * 120
    score = severity_base + exploit_bonus + cvss_component + vpr_component + epss_component
    score += age_bonus(age_days) + recency_bonus
    return int(round(clamp(score, 0, 1000)))


def compute_priority(severity, exploit_flag):
    return PRIORITY_MATRIX.get((exploit_flag, severity), ("P4", 4))


def get_csv_encoding(file_path):
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding, newline="") as handle:
                handle.readline()
            return encoding
        except UnicodeDecodeError:
            continue
    return "latin-1"


def create_connection(db_path):
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT,
            dns_name TEXT,
            vuln_name TEXT,
            cve TEXT,
            severity TEXT,
            severity_rank INTEGER,
            exploit_display TEXT,
            exploit_flag INTEGER,
            patch_priority TEXT,
            patch_priority_rank INTEGER,
            exposure_score INTEGER,
            finding TEXT,
            summary TEXT,
            description TEXT,
            remediation TEXT,
            kb_links TEXT,
            platform_details TEXT,
            first_discovered TEXT,
            last_observed TEXT,
            port TEXT,
            protocol TEXT,
            plugin_id TEXT,
            cvss_score REAL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_findings_grouping
        ON findings (
            ip_address,
            patch_priority_rank,
            severity_rank,
            exposure_score
        )
        """
    )
    return connection


def normalize_record(row, header_index, source):
    ip_address = choose_ip(pick_value(row, header_index, FIELD_ALIASES["ip_address"]))
    dns_name = choose_dns(pick_value(row, header_index, FIELD_ALIASES["dns_name"]))
    vuln_name = pick_value(row, header_index, FIELD_ALIASES["vuln_name"])
    cve = pick_value(row, header_index, FIELD_ALIASES["cve"])
    severity_raw = pick_value(row, header_index, FIELD_ALIASES["severity"])
    severity, severity_rank = normalize_severity(severity_raw)
    exploit_sc = pick_value(row, header_index, FIELD_ALIASES["exploit_sc"])
    exploit_io = pick_value(row, header_index, FIELD_ALIASES["exploit_io"])
    exploit_frameworks = " | ".join(pick_values(row, header_index, FIELD_ALIASES["exploit_frameworks"]))
    if source == "sc":
        exploit_flag = exploit_from_sc(exploit_sc)
    elif source == "io":
        exploit_flag = exploit_from_io(exploit_io)
    else:
        exploit_flag = exploit_from_sc(exploit_sc) or exploit_from_io(exploit_io)
    exploit_flag = exploit_flag or fallback_exploit_signal(exploit_frameworks)
    exploit_display = "Yes" if exploit_flag else "No"

    plugin_output = pick_value(row, header_index, FIELD_ALIASES["finding"])
    summary = pick_value(row, header_index, FIELD_ALIASES["summary"])
    description = pick_value(row, header_index, FIELD_ALIASES["description"])
    remediation = pick_value(row, header_index, FIELD_ALIASES["remediation"])
    kb_links = " | ".join(dict.fromkeys(pick_values(row, header_index, FIELD_ALIASES["kb_links"])))
    first_discovered = pick_value(row, header_index, FIELD_ALIASES["first_discovered"])
    last_observed = pick_value(row, header_index, FIELD_ALIASES["last_observed"])
    port = pick_value(row, header_index, FIELD_ALIASES["port"])
    protocol = pick_value(row, header_index, FIELD_ALIASES["protocol"])
    plugin_id = pick_value(row, header_index, FIELD_ALIASES["plugin_id"])
    cvss_score = first_number(
        pick_value(row, header_index, FIELD_ALIASES["cvss4"]),
        pick_value(row, header_index, FIELD_ALIASES["cvss3"]),
        pick_value(row, header_index, FIELD_ALIASES["cvss2"]),
    )
    vpr_score = first_number(pick_value(row, header_index, FIELD_ALIASES["vpr"]))
    epss_score = first_number(pick_value(row, header_index, FIELD_ALIASES["epss"]))
    age_days = first_number(pick_value(row, header_index, FIELD_ALIASES["age_days"]))
    recency = freshness_bonus(
        pick_value(row, header_index, FIELD_ALIASES["plugin_published"]),
        pick_value(row, header_index, FIELD_ALIASES["patch_published"]),
        pick_value(row, header_index, FIELD_ALIASES["vuln_published"]),
        first_discovered,
        last_observed,
    )
    patch_priority, patch_priority_rank = compute_priority(severity, exploit_flag)
    exposure_score = compute_exposure_score(
        severity_rank,
        exploit_flag,
        cvss_score,
        vpr_score,
        epss_score,
        age_days,
        recency,
    )

    finding = build_finding(plugin_output, protocol, port, plugin_id)
    summary = summary or summarize_text(description, fallback=vuln_name)
    description = description or plugin_output or summary
    remediation = remediation or "No remediation text was provided in the source export."
    platform_details = build_platform_details(
        pick_value(row, header_index, FIELD_ALIASES["os"]),
        pick_value(row, header_index, FIELD_ALIASES["system_type"]),
        pick_value(row, header_index, FIELD_ALIASES["repository"]),
        protocol,
        port,
    )

    return {
        "ip_address": ip_address or "Unassigned Host",
        "dns_name": dns_name,
        "vuln_name": vuln_name or "Unnamed Vulnerability",
        "cve": cve,
        "severity": severity,
        "severity_rank": severity_rank,
        "exploit_display": exploit_display,
        "exploit_flag": 1 if exploit_flag else 0,
        "patch_priority": patch_priority,
        "patch_priority_rank": patch_priority_rank,
        "exposure_score": exposure_score,
        "finding": finding,
        "summary": summary,
        "description": description,
        "remediation": remediation,
        "kb_links": kb_links,
        "platform_details": platform_details,
        "first_discovered": first_discovered,
        "last_observed": last_observed,
        "port": port,
        "protocol": protocol,
        "plugin_id": plugin_id,
        "cvss_score": cvss_score if cvss_score is not None else None,
    }


def serialize_preview_rows(rows):
    preview = []
    for row in rows:
        preview.append(
            {
                "IP Address": row["ip_address"],
                "DNS Name": row["dns_name"],
                "Vulnerability Name": row["vuln_name"],
                "CVE": row["cve"],
                "Severity": row["severity"],
                "Exploit?": row["exploit_display"],
                "Patch Priority": row["patch_priority"],
                "Asset Exposure (on 1000)": row["exposure_score"],
                "Vulnerability Finding": row["finding"],
                "Summary": row["summary"],
                "Description": row["description"],
                "Remediation": row["remediation"],
                "KB Links": row["kb_links"],
                "Platform Details": row["platform_details"],
                "First Discovered": row["first_discovered"],
                "Last Observed": row["last_observed"],
            }
        )
    return preview


def extract_group_summaries(connection):
    query = """
        SELECT
            ip_address,
            MAX(COALESCE(NULLIF(dns_name, ''), '')) AS dns_name,
            COUNT(*) AS total_findings,
            SUM(CASE WHEN severity = 'Critical' THEN 1 ELSE 0 END) AS critical_count,
            SUM(CASE WHEN severity = 'High' THEN 1 ELSE 0 END) AS high_count,
            SUM(CASE WHEN severity = 'Medium' THEN 1 ELSE 0 END) AS medium_count,
            SUM(CASE WHEN severity = 'Low' THEN 1 ELSE 0 END) AS low_count,
            SUM(CASE WHEN severity = 'Info' THEN 1 ELSE 0 END) AS info_count,
            SUM(CASE WHEN patch_priority = 'P1' THEN 1 ELSE 0 END) AS p1_count,
            MAX(exposure_score) AS max_exposure,
            MIN(patch_priority_rank) AS best_priority_rank,
            MAX(severity_rank) AS highest_severity_rank
        FROM findings
        GROUP BY ip_address
        ORDER BY
            best_priority_rank ASC,
            critical_count DESC,
            high_count DESC,
            max_exposure DESC,
            total_findings DESC,
            ip_address ASC
    """
    connection.row_factory = sqlite3.Row
    return [dict(row) for row in connection.execute(query)]


def fetch_group_rows(connection, ip_address):
    connection.row_factory = sqlite3.Row
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
    return [dict(row) for row in connection.execute(query, (ip_address,))]


def parse_and_stage_csv(file_path, db_path, progress_callback=None):
    encoding = get_csv_encoding(file_path)
    connection = create_connection(db_path)
    stats = Counter()
    unique_ips = set()

    try:
        with open(file_path, "r", encoding=encoding, newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            header_index = build_header_index(headers)
            source = detect_source(headers)
            placeholders = ", ".join(["?"] * len(DB_COLUMNS))
            insert_sql = f"INSERT INTO findings ({', '.join(DB_COLUMNS)}) VALUES ({placeholders})"

            batch = []
            for row_number, row in enumerate(reader, start=1):
                normalized = normalize_record(row, header_index, source)
                batch.append(tuple(normalized[column] for column in DB_COLUMNS))
                unique_ips.add(normalized["ip_address"])
                stats["total_findings"] += 1
                stats[f"severity_{normalized['severity'].lower()}"] += 1
                stats[f"priority_{normalized['patch_priority'].lower()}"] += 1

                if len(batch) >= 1000:
                    connection.executemany(insert_sql, batch)
                    connection.commit()
                    batch.clear()

                if progress_callback and row_number % 1000 == 0:
                    progress_callback(
                        min(36, 6 + (row_number // 1000)),
                        f"Parsing row {row_number:,}",
                    )

            if batch:
                connection.executemany(insert_sql, batch)
                connection.commit()

        stats["total_ips"] = len(unique_ips)
        group_summaries = extract_group_summaries(connection)
        preview_groups = []
        for group in group_summaries[:3]:
            preview_groups.append(
                {
                    "summary": group,
                    "rows": serialize_preview_rows(fetch_group_rows(connection, group["ip_address"])[:8]),
                }
            )

        return {
            "headers": headers,
            "source": source,
            "stats": {
                "total_ips": stats["total_ips"],
                "total_findings": stats["total_findings"],
                "critical": stats["severity_critical"],
                "high": stats["severity_high"],
                "medium": stats["severity_medium"],
                "low": stats["severity_low"],
                "info": stats["severity_info"],
                "p1": stats["priority_p1"],
                "p2": stats["priority_p2"],
                "p3": stats["priority_p3"],
                "p4": stats["priority_p4"],
            },
            "group_summaries": group_summaries,
            "preview_groups": preview_groups,
        }
    finally:
        connection.close()
