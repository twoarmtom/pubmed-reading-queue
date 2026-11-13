#!/usr/bin/env python3
"""Fetch PubMed articles for a personal PubMed reading queue (configured by config.json).

Usage (every command takes --config CONFIG.json):
  python3 -I fetch_pubmed.py START(YYYY/MM/DD) END(YYYY/MM/DD) OUT.json --config C   # fresh pull
  python3 -I fetch_pubmed.py update QUEUE.json --config C                            # add new articles in place
  python3 -I fetch_pubmed.py update QUEUE.json --import CONNECTOR.json --config C    # same, from PubMed-connector metadata
  python3 -I fetch_pubmed.py query --config C                                        # print the PubMed query
  Add --signed-off STATUS_DIR (the artifact's status/*.json documents) to drop articles signed off
  more than --keep-days (default 30) days ago and to never re-add signed-off articles.
  An empty or missing QUEUE.json is started fresh, looking back --init-days (default 60).
Searches by Entrez date (when PubMed added the record), same terms as the old
pubmed-digest skill, and writes one JSON list of article dicts.
"""
import json, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

EU = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
CFG = {}

def load_config(path):
    """config.json: queue_title, terms (PubMed expressions, ORed), exclude_terms (ORed, NOT-ed),
    exclude_regex (post-filter on title/journal), categories [[name, regex]], high_impact (NLM
    journal abbreviations), high_impact_prefixes."""
    global CFG
    CFG = json.load(open(path))
    CFG["_ex"] = re.compile(CFG["exclude_regex"], re.I) if CFG.get("exclude_regex") else None
    CFG["_cats"] = [(n, re.compile(rx, re.I)) for n, rx in CFG.get("categories", [])]
    CFG["_hi"] = set(CFG.get("high_impact", []))
    CFG["_hip"] = tuple(CFG.get("high_impact_prefixes", []))

def build_terms():
    q = "(" + " OR ".join(CFG["terms"]) + ")"
    if CFG.get("exclude_terms"):
        q += " NOT (" + " OR ".join(CFG["exclude_terms"]) + ")"
    return q

def get(url, params, tries=4):
    params = dict(params, tool="pubmed-reading-queue")
    data = urllib.parse.urlencode(params).encode()
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=60) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(2 + i * 3)

def text(el):
    return "".join(el.itertext()).strip() if el is not None else ""

def study_type(pts):
    p = " | ".join(pts).lower()
    if "meta-analysis" in p or "systematic review" in p: return "Systematic review / MA"
    if "randomized controlled trial" in p: return "RCT"
    if "practice guideline" in p or p.startswith("guideline") or "| guideline" in p: return "Guideline"
    if "review" in p: return "Review"
    if "case reports" in p: return "Case report"
    if any(x in p for x in ("letter", "comment", "editorial")): return "Letter / editorial"
    if "clinical trial" in p: return "Clinical trial"
    if "observational study" in p: return "Observational"
    return ""

def pub_date(art):
    for path in ("Article/ArticleDate", "Article/Journal/JournalIssue/PubDate"):
        d = art.find(path)
        if d is not None and d.findtext("Year"):
            y = d.findtext("Year"); m = d.findtext("Month") or "1"; day = d.findtext("Day") or "1"
            months = "jan feb mar apr may jun jul aug sep oct nov dec".split()
            if not m.isdigit(): m = str(months.index(m[:3].lower()) + 1) if m[:3].lower() in months else "1"
            return f"{y}-{int(m):02d}-{int(day):02d}"
    return ""

def parse(xml):
    out = []
    for pa in ET.fromstring(xml).findall("PubmedArticle"):
        mc = pa.find("MedlineCitation"); art = mc.find("Article")
        pmid = mc.findtext("PMID")
        title = text(art.find("ArticleTitle")).rstrip()
        abst = []
        for at in art.findall("Abstract/AbstractText"):
            label = at.get("Label")
            abst.append({"label": label.title() if label and label.isupper() else label, "text": text(at)})
        auths = []
        for a in art.findall("AuthorList/Author"):
            if a.findtext("LastName"): auths.append(f"{a.findtext('LastName')} {a.findtext('Initials') or ''}".strip())
            elif a.findtext("CollectiveName"): auths.append(a.findtext("CollectiveName"))
        authors = (auths[0] + " et al.") if len(auths) > 2 else ", ".join(auths)
        journal = text(art.find("Journal/Title"))
        abbr = mc.findtext("MedlineJournalInfo/MedlineTA") or art.findtext("Journal/ISOAbbreviation") or ""
        doi = ""
        for aid in pa.findall("PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi": doi = aid.text or ""
        if not doi:
            for e in art.findall("ELocationID"):
                if e.get("EIdType") == "doi": doi = e.text or ""
        added = ""
        for h in pa.findall("PubmedData/History/PubMedPubDate"):
            if h.get("PubStatus") in ("entrez", "pubmed"):
                added = f"{h.findtext('Year')}-{int(h.findtext('Month')):02d}-{int(h.findtext('Day')):02d}"; break
        pts = [text(p) for p in art.findall("PublicationTypeList/PublicationType")]
        kws = " ".join(text(k) for k in mc.findall("KeywordList/Keyword"))
        mesh = " ".join(text(d) for d in mc.findall("MeshHeadingList/MeshHeading/DescriptorName"))
        a = finish(pmid, title, journal, abbr, authors, pub_date(art), added, doi, pts, f"{kws} {mesh}", abst)
        if a: out.append(a)
    return out

def finish(pmid, title, journal, abbr, authors, published, added, doi, pts, extra, abst):
    """Apply the exclusion filter, topic, high-impact flag and study type. None = drop."""
    ex = CFG["_ex"]
    if ex and (ex.search(title) or ex.search(journal)):
        return None
    cat = next((c for c, rx in CFG["_cats"] if rx.search(f"{title} {extra}")), "Other")
    hi = abbr in CFG["_hi"] or (bool(CFG["_hip"]) and abbr.startswith(CFG["_hip"]))
    return {"pmid": pmid, "title": title, "journal": journal, "abbr": abbr, "authors": authors,
            "published": published, "added": added, "doi": doi, "type": study_type(pts),
            "category": cat, "hi": hi, "abstract": abst}

def from_connector(items, added):
    """Convert PubMed-connector get_article_metadata 'articles' entries to queue articles."""
    out = []
    for it in items:
        ids = it.get("identifiers") or {}
        j = it.get("journal") or {}
        au = [f"{a.get('last_name','')} {a.get('initials','')}".strip() for a in it.get("authors") or [] if a.get("last_name")]
        authors = (au[0] + " et al.") if len(au) > 2 else ", ".join(au)
        pd = it.get("publication_date") or {}
        published = ""
        if pd.get("year"):
            m = pd.get("month") or "1"; d = pd.get("day") or "1"
            published = f"{pd['year']}-{int(m) if str(m).isdigit() else 1:02d}-{int(d) if str(d).isdigit() else 1:02d}"
        abst = [{"label": None, "text": t.strip()} for t in (it.get("abstract") or "").split("\n\n") if t.strip()]
        a = finish(str(ids.get("pmid") or it.get("pmid")), (it.get("title") or "").strip(), j.get("title", ""),
                   j.get("iso_abbreviation", ""), authors, published, added, ids.get("doi") or it.get("doi") or "",
                   it.get("article_types") or [], " ".join(it.get("keywords") or []), abst)
        if a: out.append(a)
    return out

def fetch(start, end):
    term = f"{build_terms()} AND {start}:{end}[edat]"
    r = json.loads(get(EU + "esearch.fcgi", {"db": "pubmed", "term": term, "usehistory": "y", "retmode": "json", "retmax": 0}))
    es = r["esearchresult"]; count = int(es["count"])
    print(f"{count} PMIDs", file=sys.stderr)
    arts = []
    for s in range(0, count, 200):
        xml = get(EU + "efetch.fcgi", {"db": "pubmed", "query_key": es["querykey"], "WebEnv": es["webenv"],
                                        "retstart": s, "retmax": 200, "retmode": "xml"})
        arts += parse(xml); print(f"  {min(s+200, count)}/{count}", file=sys.stderr); time.sleep(0.4)
    return arts

def load_signed_off(folder):
    """Read the artifact's status/<YYYY-MM> documents (saved as JSON files) into {pmid: signedOffAtMs}."""
    import glob, os
    done = {}
    for f in glob.glob(os.path.join(folder, "*.json")):
        d = json.load(open(f))
        items = d.get("items") if "items" in d else (d.get("data") or {}).get("items", {})
        for k, v in (items or {}).items():
            if v: done[str(k)] = v
    return done

def update(path, imported=None, signed_off=None, keep_days=30, init_days=60):
    """Add articles PubMed gained since the queue's newest one (3-day overlap) and drop articles
    signed off more than keep_days ago. Rewrites the queue file in place."""
    import datetime, os
    try: cur = json.load(open(path)); arts = cur["articles"] if isinstance(cur, dict) else cur
    except (FileNotFoundError, ValueError): arts = []
    today = datetime.date.today()
    done = load_signed_off(signed_off) if signed_off else {}
    if imported:
        raw = json.load(open(imported)); raw = raw.get("articles", raw) if isinstance(raw, dict) else raw
        new = from_connector(raw, today.isoformat())
    else:
        if arts:
            newest = max(a["added"] for a in arts)
            start = (datetime.date.fromisoformat(newest) - datetime.timedelta(days=3)).strftime("%Y/%m/%d")
        else:
            start = (today - datetime.timedelta(days=init_days)).strftime("%Y/%m/%d")
        new = fetch(start, today.strftime("%Y/%m/%d"))
    have = {a["pmid"] for a in arts} | set(done)  # never re-add a signed-off article
    added = [a for a in new if not (a["pmid"] in have or have.add(a["pmid"]))]  # skips known and repeated PMIDs
    cutoff = (datetime.datetime.now().timestamp() - keep_days * 86400) * 1000
    kept = [a for a in arts if not (a["pmid"] in done and done[a["pmid"]] < cutoff)]
    pruned = len(arts) - len(kept)
    merged = sorted(added + kept, key=lambda a: (a["added"], a["pmid"]), reverse=True)
    json.dump({"updated": today.isoformat(), "articles": merged}, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
    print(json.dumps({"new": len(added), "new_high_impact": sum(a["hi"] for a in added), "pruned": pruned,
                      "total": len(merged), "bytes": os.path.getsize(path)}))

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--config" not in args: sys.exit("missing --config CONFIG.json")
    i = args.index("--config"); load_config(args[i + 1]); del args[i:i + 2]
    if args[0] == "query":
        print(build_terms())
    elif args[0] == "update":
        opts = dict(zip(args[2::2], args[3::2]))
        update(args[1], opts.get("--import"), opts.get("--signed-off"), int(opts.get("--keep-days", 30)), int(opts.get("--init-days", 60)))
    else:
        start, end, outpath = args[:3]
        arts = fetch(start, end)
        seen = set(); arts = [a for a in arts if not (a["pmid"] in seen or seen.add(a["pmid"]))]
        arts.sort(key=lambda a: (a["added"], a["pmid"]), reverse=True)
        json.dump({"updated": end.replace("/", "-"), "articles": arts}, open(outpath, "w"), ensure_ascii=False, separators=(",", ":"))
        print(f"wrote {len(arts)} articles ({sum(a['hi'] for a in arts)} high-impact)", file=sys.stderr)
