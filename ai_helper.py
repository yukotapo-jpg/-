import os
import asyncio
from google import genai
from google.genai import types

def _call_gemini_sync(prompt: str, system_prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "❌ Renderの環境変数に `GEMINI_API_KEY` が設定されていません！"

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=1500,
        )
    )
    return response.text or "（回答を生成できませんでした）"

async def ask_gemini(prompt: str, character: str = "フレンドリーな友達") -> str:
    system_prompt = (
        f"あなたはDiscordサーバーに常駐するAIアシスタントです。"
        f"口調やキャラクター設定は「{character}」になりきって回答してください。"
        f"Discordのチャットで読みやすいように、簡潔で分かりやすくまとめてください。"
    )
    try:
        # Botの動作を止めないように別スレッドで非同期実行する
        return await asyncio.to_thread(_call_gemini_sync, prompt, system_prompt)
    except Exception as e:
        return f"❌ AIとの通信中にエラーが発生しました: `{e}`"
