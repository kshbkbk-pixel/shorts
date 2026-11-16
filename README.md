# shorts

주제 한 줄로 60초 한국어 세로 쇼츠를 만드는 파이프라인입니다. 지금은 1주차 단계로, 웹 화면 없이 명령줄에서 돌아갑니다.

```
주제 → 대본(Claude) → [사람이 대본 수정] → 장면별 이미지 + 내레이션(병렬) → 자막 → 1080x1920 MP4 + 원가 보고서
```

## 준비

- Python 3.11 이상, ffmpeg
- 한글 폰트 (Noto Sans KR 또는 Pretendard 권장, `SHORTS_FONT` 로 지정)

```bash
pip install -e ".[dev]"
cp .env.example .env   # 쓸 공급자의 키만 채우면 됩니다
```

## 사용법

```bash
# 1) 대본만 만들고 runs/cat/script.json 을 직접 고친다
python -m shorts script --topic "고양이가 상자를 좋아하는 진짜 이유" --genre 상식 --out runs/cat

# 2) 고친 대본으로 영상을 만든다
python -m shorts render --script runs/cat/script.json --tts google --images fal-schnell

# 한 번에
python -m shorts make --topic "..." --tts google --images fal-schnell --out runs/demo

# 공급자 비교: 같은 대본 앞 3장면으로 음성·이미지를 만들어 runs/compare/index.html 에 나란히 보여준다
python -m shorts compare --script runs/cat/script.json --tts openai,google,elevenlabs --images fal-schnell,fal-dev,openai
```

결과 폴더에는 `final.mp4`, `script.json`, 호출별 비용이 담긴 `report.json` 이 생깁니다.
API 키 없이 흐름만 확인하려면 `--writer mock --tts mock --images mock` 을 쓰세요.

## 공급자

| 단계 | 이름 | 필요한 키 | 근사 단가 |
| --- | --- | --- | --- |
| 대본 | `claude` | `ANTHROPIC_API_KEY` | 편당 약 $0.03~0.05 (Opus 5.5, effort low) |
| 음성 | `google` | `GOOGLE_TTS_API_KEY` | 1천 자당 약 $0.016 |
| 음성 | `openai` | `OPENAI_API_KEY` | 1천 자당 약 $0.015 |
| 음성 | `elevenlabs` | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | 1천 자당 약 $0.18 |
| 이미지 | `fal-schnell` | `FAL_KEY` | 장당 약 $0.003 |
| 이미지 | `fal-dev` | `FAL_KEY` | 장당 약 $0.025 |
| 이미지 | `openai` | `OPENAI_API_KEY` | 장당 약 $0.04 |

단가는 코드(`tts.py`, `images.py`, `script.py`)에 적힌 근사치이고, 실제 청구액은 각 공급자 가격표로 확인해야 합니다.

## 테스트

```bash
pytest
```

테스트는 mock 공급자만 써서 키와 네트워크 없이 돌아가고, 실제로 1080x1920 영상을 렌더합니다.

## 아직 안 된 것

- 웹 화면, 로그인, 결제 (2주차부터)
- 단어 단위 자막 타이밍: 지금은 장면 음성 길이를 글자 수 비율로 나눕니다
- 실제 공급자 호출 검증: 요청 형식은 각 사의 공개 API 문서를 기준으로 작성했고, 키를 넣고 한 번씩 돌려봐야 합니다
