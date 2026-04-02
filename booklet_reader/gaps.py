from datetime import date

def _parse_date(date_str):
    if isinstance(date_str, date):
        return date_str
    return date.fromisoformat(str(date_str))

def _find_performer(name, performers_config):
    for p in performers_config:
        if p["name"] == name:
            return p
    return None

def _find_instrument(performer_config, instrument_name):
    for inst in performer_config["instruments"]:
        aliases = [a.strip() for a in inst["names"].split("/")]
        if instrument_name in aliases:
            return inst
    return None

def _lookup_by_date(entries, performance_date):
    if not entries:
        return None
    perf_date = _parse_date(performance_date)
    for entry in entries:
        start = _parse_date(entry["from"])
        end = _parse_date(entry["to"]) if "to" in entry and entry["to"] else None
        if perf_date >= start and (end is None or perf_date <= end):
            return entry["name"]
    return None

def fill_gaps(results, performers_config):
    for result in results:
        performer = _find_performer(result["performer"], performers_config)
        if performer is None:
            continue
        instrument = _find_instrument(performer, result["instrument"])
        if instrument is None:
            continue
        perf_date = result.get("performance_date")
        if perf_date is None:
            continue
        if result.get("teacher") is None:
            teachers = instrument.get("teachers", [])
            result["teacher"] = _lookup_by_date(teachers, perf_date)
        if result.get("accompanist") is None:
            accompanists = instrument.get("accompanists", [])
            result["accompanist"] = _lookup_by_date(accompanists, perf_date)
    return results
