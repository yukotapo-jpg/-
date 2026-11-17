import os
import time
import asyncio
from google import genai
from google.genai import types

def _call_gemini_sync(prompt: str, system_prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "❌ Renderの環境変数に `GEMINI_API_KEY` が設定されていません！"

    client = genai.Client(api_key=api_key)
    
    # 混雑(503)対策：最大3回まで自動で再試行する
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=1500,
                )
            )
            return response.text or "（回答を生成できませんでした）"
        except Exception as e:
            if "503" in str(e) and attempt < 2:
                time.sleep(2)
                continue
            raise e

async def ask_gemini(prompt: str, character: str = "フレンドリーな友達") -> str:
    system_prompt = (
        f"あなたはDiscordサーバーに常駐するAIアシスタントです。"
        f"口調やキャラクター設定は「{character}」になりきって回答してください。"
        f"Discordのチャットで読みやすいように、簡潔で分かりやすくまとめてください。"
    )
    try:
        return await asyncio.to_thread(_call_gemini_sync, prompt, system_prompt)
    except Exception as e:
        return f"❌ AIサーバーが混雑しています。少し時間を置いてもう一度試してね！\n（詳細: `{e}`）"
