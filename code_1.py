from flask import Flask, request, abort, jsonify
import google.generativeai as genai
import requests
import json

# 天氣API URL
url = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/F-C0032-003?Authorization=rdec-key-123-45678-011121314&format=JSON"

api_key = 'Your Key'
genai.configure(api_key=api_key)

#選擇Gemini模型
model = genai.GenerativeModel('gemini-2.0-flash')

#儲存歷史對話
chat = model.start_chat(history=[])

# 儲存用戶是否正在與 Gemini 聊天的狀態
user_states = {}

# 狀態管理
user_states = {}       # 是否啟用 Gemini 聊天模式
user_histories = {}    # 儲存使用者對話紀錄

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    StickerMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    StickerMessageContent,
    VideoMessageContent,
    LocationMessageContent
)

app = Flask(__name__)

configuration = Configuration(access_token='A7YiF1LRQnoDk2goRD5P8dcYjhVFgJ11o4rYMcFLGeoJA1Cs3YKV8yw48MMCUgsr1B7cGK40jpUURJ90SIWpRia22GKaFiG/Za/dfOuua/hx9NAxS85Jgpi16rV3/hniUfHf8rJeBpiBEuHq3t+MAAdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('cc5960e4752f2daa68e68ef46370a1ba')


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        if isinstance(event.message, TextMessageContent):
            user_id = event.source.user_id
            text = event.message.text.strip()

            # 初始化歷史紀錄
            if user_id not in user_histories:
                user_histories[user_id] = []
                print(f"使用者 ID：{user_id}")

            if text == "愛笑在哪裡":
                user_states[user_id] = True
                reply = "愛笑來了！怎麼了嗎？"

            elif text == "謝謝愛笑":
                user_states[user_id] = False
                reply = "祝您有美好的一天~"
						
            elif user_states.get(user_id):
                # 新建獨立 chat 物件並包含歷史紀錄
                chat_session = model.start_chat(history=user_histories[user_id])
                gemini_response = chat_session.send_message(text)
                reply = gemini_response.text

                # 儲存歷史對話
                user_histories[user_id].append({"role": "user", "parts": [text]})
                user_histories[user_id].append({"role": "model", "parts": [reply]})
            elif text == "天氣查詢":
                weather = get_weather()
                reply = weather
            else:
                reply = f"你好這是文字訊息 我喜歡貼圖"

            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )

            
        elif isinstance(event.message, ImageMessageContent):
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="真漂亮的照片呀")]
                )
            )
        elif isinstance(event.message, StickerMessageContent):
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[StickerMessage(package_id='1', sticker_id='1')]
                )
            )
        elif isinstance(event.message, VideoMessageContent):
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="哈哈哈這影片怎麼那麼好笑這是你自己拍的嗎怎麼那麼好笑哈哈哈哈")]
                )
            )
        elif isinstance(event.message, LocationMessageContent):
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="真假啦你在那裡喔？")]
                )
            )
        else:
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="你要確定ㄟ")]
                )
            )

# RESTful API：取得使用者歷史對話
@app.route("/history/<user_id>", methods=["GET"])
def get_history(user_id):
    history = user_histories.get(user_id)
    if history is None:
        return jsonify({"message": "沒有找到對話紀錄"}), 404
    return jsonify(history)

# RESTful API：刪除使用者歷史對話
@app.route("/history/<user_id>", methods=["DELETE"])
def delete_history(user_id):
    if user_id in user_histories:
        del user_histories[user_id]
        return jsonify({"message": "已刪除對話紀錄"})
    else:
        return jsonify({"message": "找不到該使用者的紀錄"}), 404


def get_weather():
    try:
        response = requests.get(url)
        data = response.json()
        
        # 找出台北市的資料
        locations = data['cwaopendata']['dataset']['location']
        taipei_weather = next(loc for loc in locations if loc['locationName'] == '臺北市')
        
        result = "台北市七天天氣預報：\n"
        
        for time_data in taipei_weather['weatherElement'][0]['time']:
            start_date = time_data['startTime'].split("T")[0]
            weather = time_data['parameter']['parameterName']
            result += f"{start_date}：{weather}\n"
        
        return result
    except Exception as e:
        return f"⚠️ 天氣查詢失敗：{e}"


if __name__ == "__main__":
    app.run()