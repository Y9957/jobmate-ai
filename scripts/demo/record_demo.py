"""Record the README demo: drive the running app with Playwright, caption each step, save a GIF.

    docker compose up -d --build          # and Ollama with qwen3:8b running
    python scripts/demo/record_demo.py --reset

--reset deletes every resume, job and application first, so the demo starts empty.
Only use it on a local demo database.
"""

import argparse
import io
import json
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://localhost:3000"
VIEW = {"width": 1280, "height": 800}
OUT_WIDTH = 1280
FONT = "C:/Windows/Fonts/malgunbd.ttf"


def api(method: str, path: str) -> object:
    req = urllib.request.Request(BASE + path, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return json.loads(body) if body else None


def reset() -> None:
    for kind in ("applications", "jobs", "resumes"):  # analyses go with resumes/jobs (cascade)
        for item in api("GET", f"/api/{kind}"):
            api("DELETE", f"/api/{kind}/{item['id']}")


class Recorder:
    def __init__(self, page: Page, font_path: str):
        self.page = page
        self.frames: list[tuple[Image.Image, int]] = []
        self.font = ImageFont.truetype(font_path, 26)

    def shot(self, caption: str, ms: int = 2600) -> None:
        raw = Image.open(io.BytesIO(self.page.screenshot())).convert("RGB")
        bar_h = 64
        frame = Image.new("RGB", (raw.width, raw.height + bar_h), (29, 32, 37))
        frame.paste(raw, (0, bar_h))
        ImageDraw.Draw(frame).text((24, bar_h // 2), caption, font=self.font, fill=(255, 255, 255), anchor="lm")
        h = round(frame.height * OUT_WIDTH / frame.width)
        self.frames.append((frame.resize((OUT_WIDTH, h), Image.LANCZOS), ms))

    def save(self, path: Path) -> None:
        images = [
            f.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f, _ in self.frames
        ]
        images[0].save(
            path,
            save_all=True,
            append_images=images[1:],
            duration=[ms for _, ms in self.frames],
            loop=0,
            optimize=True,
        )


def scroll_to(page: Page, selector_text: str) -> None:
    page.get_by_text(selector_text, exact=False).first.scroll_into_view_if_needed()
    page.evaluate("window.scrollBy(0, -90)")
    page.wait_for_timeout(300)


def run(out: Path, font: str) -> None:
    resume = (ROOT / "backend/samples/resume_sample.txt").read_text(encoding="utf-8")
    job = (ROOT / "backend/samples/job_sample.txt").read_text(encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEW, locale="ko-KR")
        rec = Recorder(page, font)

        page.goto(BASE + "/")
        page.wait_for_selector("text=등록한 이력서")
        rec.shot("JobMate AI — 이력서와 공고를 대조해, LLM이 든 근거가 진짜인지 검증합니다", 3000)

        page.goto(BASE + "/resumes")
        page.get_by_label("이름").fill("가상 이력서 (샘플)")
        page.get_by_label("이력서 내용").fill(resume)
        rec.shot("① 이력서 등록 — 연락처는 저장 전에 가려지고, PDF 원본은 저장하지 않습니다")
        page.get_by_role("button", name="저장").click()
        page.get_by_role("button", name="가상 이력서 (샘플)").click()
        stored = page.locator("pre.resume")
        stored.wait_for()
        stored.evaluate("el => el.closest('.card').scrollIntoView({block: 'start'})")
        page.wait_for_timeout(300)
        rec.shot("저장된 이력서 — 전화번호·이메일이 [PHONE]·[EMAIL]로 가려졌고, 모델에도 이 텍스트만 갑니다", 3600)

        page.goto(BASE + "/jobs")
        page.get_by_label("회사").fill("가상테크")
        page.get_by_label("포지션").fill("AI 서비스 백엔드 개발자")
        page.get_by_label("공고 본문").fill(job)
        rec.shot("② 채용공고 본문을 붙여넣어 등록")
        page.get_by_role("button", name="저장").click()
        page.wait_for_selector("text=가상테크 · AI 서비스 백엔드 개발자")

        page.goto(BASE + "/analyses")
        page.get_by_label("이력서", exact=True).select_option(label="가상 이력서 (샘플)")
        page.get_by_label("공고", exact=True).select_option(label="가상테크 · AI 서비스 백엔드 개발자")
        rec.shot("③ 이력서와 공고를 골라 분석 시작")
        page.get_by_role("button", name="분석 시작").click()

        page.wait_for_url("**/analyses/*")
        page.wait_for_selector("text=로컬 모델로 분석 중")
        rec.shot("④ 로컬 LLM(qwen3:8b): 요구조건 추출 → 근거 매칭 → 원문 대조 → 의미 검증", 3000)
        started = time.time()
        page.wait_for_selector("text=판정 이유", timeout=240_000)
        print(f"analysis finished in {time.time() - started:.0f}s")
        page.evaluate("window.scrollTo(0, 0)")
        rec.shot("⑤ 점수 대신 유형별 충족 수, 요구조건마다 이력서 근거와 검증 결과", 4200)

        scroll_to(page, "Kubernetes")
        rec.shot("근거가 없으면 미충족 — 이력서에 Kubernetes 경험이 없습니다", 3200)

        card = page.locator(".evidence", has_text="Kubernetes")
        card.get_by_role("button", name="근거 수정").click()
        card.get_by_label("이력서 근거 문장").fill("Kubernetes 클러스터를 3년간 운영했습니다.")
        card.scroll_into_view_if_needed()
        rec.shot("⑥ 사용자가 근거를 고쳐도 다시 검증합니다 — 이력서에 없는 문장을 넣으면…", 3000)
        card.get_by_role("button", name="저장하고 재검증").click()
        card.get_by_text("인용문이 이력서 원문에 없습니다").wait_for()
        card.scroll_into_view_if_needed()
        rec.shot("원문 대조에서 거부 — 이력서에 없는 문장은 근거가 될 수 없습니다", 4200)

        page.goto(BASE + "/")
        page.wait_for_selector("text=최근 분석")
        page.wait_for_selector("text=완료")
        rec.shot("대시보드에서 분석과 지원 현황을 한눈에", 3500)

        rec.save(out)
        browser.close()
    print(f"saved {out} ({out.stat().st_size / 1_048_576:.1f} MB, {len(rec.frames)} frames)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reset", action="store_true", help="delete all resumes, jobs and applications first")
    p.add_argument("--out", type=Path, default=ROOT / "docs/images/demo.gif")
    p.add_argument("--font", default=FONT, help="a TTF font with Korean glyphs")
    a = p.parse_args()
    if a.reset:
        reset()
    run(a.out, a.font)


if __name__ == "__main__":
    main()
