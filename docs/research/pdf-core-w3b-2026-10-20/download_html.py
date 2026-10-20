"""Version-pinned public HTML fetches, one request per three seconds, no inference."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import time

from lxml import html
import requests

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "pdf-core-w3-structured-elements-2026-10-20"


def save(path, data):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def main():
    jobs = json.loads((OLD / "jobs.json").read_text())["jobs"]
    records = []
    session = requests.Session()
    session.headers["User-Agent"] = "W3b-local-paper-qualification/1.0 (public HTML research; CPU only)"
    for job in jobs:
        version = job["arxiv_version"]
        recent = int(version[:2]) >= 23
        urls = [f"https://arxiv.org/html/{version}", f"https://ar5iv.labs.arxiv.org/html/{version}"]
        if not recent:
            urls.reverse()
        record = dict(job_id=job["id"], family=job["family"], arxiv_version=version,
                      pdf=job["pdf"], pdf_sha256=job["pdf_sha256"], first=job["first"], last=job["last"],
                      title=job["title"], attempts=[], status="UNAVAILABLE")
        for index, url in enumerate(urls):
            started = time.monotonic()
            attempt = dict(requested_url=url, retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
            try:
                response = session.get(url, timeout=(10, 35), allow_redirects=True)
                content = response.content
                digest = hashlib.sha256(content).hexdigest()
                failed_path = HERE / "network" / f"{job['id']}-{index}.response"
                failed_path.write_bytes(content)
                attempt.update(http_status=response.status_code, final_url=response.url, sha256=digest,
                               bytes=len(content), content_type=response.headers.get("Content-Type"), response_path=str(failed_path))
                tree = html.fromstring(content) if content else None
                documents = tree.xpath("//*[contains(concat(' ',normalize-space(@class),' '),' ltx_document ')]") if tree is not None else []
                if response.status_code == 200 and documents:
                    target = HERE / "html" / f"{job['id']}.html"
                    target.write_bytes(content)
                    text = content.decode(response.encoding or "utf-8", errors="replace")
                    generators = tree.xpath("//meta[translate(@name,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='generator']/@content")
                    latexml = re.findall(r"LaTeXML(?:\s+version|\s+Version)?[^<>\n]{0,180}", text)
                    record.update(status="AVAILABLE", html_path=str(target), sha256=digest, requested_url=url,
                                  final_url=response.url, http_status=response.status_code,
                                  retrieved_utc=attempt["retrieved_utc"], generator_meta=generators,
                                  latexml_version_evidence=latexml[-8:],
                                  canonical_urls=tree.xpath("//link[@rel='canonical']/@href"),
                                  citation_meta=[dict(name=m.get("name"), content=m.get("content")) for m in tree.xpath("//meta[starts-with(@name,'citation_')]")],
                                  article_title=tree.xpath("string(//title)"),
                                  html_tables=len(tree.xpath("//table")), math_alttext=len(tree.xpath("//*[local-name()='math'][@alttext]")))
                else:
                    attempt["reason"] = "HTTP failure or no LaTeXML document body"
            except Exception as error:
                attempt["error"] = f"{type(error).__name__}: {error}"
            attempt["wall_seconds"] = time.monotonic() - started
            record["attempts"].append(attempt)
            time.sleep(max(0, 3 - (time.monotonic() - started)))
            if record["status"] == "AVAILABLE":
                break
        records.append(record)
        save(HERE / "html-manifest.json", dict(complete=len(records) == len(jobs), requested_documents=len(jobs),
             completed_documents=len(records), available=sum(r["status"] == "AVAILABLE" for r in records),
             version_policy="Exact frozen version only; ordered arxiv/ar5iv endpoints; no silent latest-version fallback", jobs=records))
        print(json.dumps(dict(job_id=job["id"], status=record["status"], completed=len(records)), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
