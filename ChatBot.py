import json
import os
import requests
import boto3
import time
import decimal


def next_seq(table, tablename):
    # DynamoDBのテーブルを更新するためのupdate_item関数を呼び出す
    response= table.update_item(
        Key={
            'sequence' : tablename  # プライマリキーを指定する
        },
        UpdateExpression = "set seq = seq + :val",  # seq属性を更新する
        ExpressionAttributeValues={
            ':val' : 1  # seqに加算する値を指定する
        },
        ReturnValues='UPDATED_NEW'  # 更新後の項目値を返すように指定する
        )
    # 更新後のseqの値を返す
    return response['Attributes']['seq']


def lambda_handler(event, context):
    #環境変数より値取得
    chatgpt_api_key = os.environ['ChatGPT_API_KEY']
    line_api_key = os.environ['LINE_API_KEY']
    
    # LINE Messaging APIからのリクエストをパースする
    body = json.loads(event['body'])
    
    # LINE Messaging APIから送信されたイベントオブジェクトを取得する
    events = body.get('events', [])
    
    # イベントオブジェクトが空の場合は、何もしない
    if not events:
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'success'})
        }
    
    # イベントオブジェクトを処理する
    reply_token = events[0]['replyToken']
    message = events[0]['message']['text']
    user_id = events[0]['source']['userId']
    
    #ChatGptのリクエストURL
    url = "https://api.openai.com/v1/chat/completions"
    
    #ChatGPTに対するリクエストを作成する
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + chatgpt_api_key
    }
    
    #モデルは「gpt-3.5-turbo」を使用。
    payload = {
      "model": "gpt-3.5-turbo",
      "messages": [{"role": "user", "content": message}]
    }
    
    #質問に対する応答文取得。
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    response_data = json.loads(response.content.decode('utf-8'))
    
    #改行コードを消す。
    response_data = response_data['choices'][0]['message']['content'].lstrip()
    
    #DynamoDBにメッセージの内容を書き込む処理を以下より記載。
    dynamodb = boto3.resource('dynamodb')
    
    #シーケンスデータ取得
    seqtable = dynamodb.Table('sequence')
    nextseq = next_seq(seqtable, 'message')
    
    #現在のUNIXスタンプを得る。
    now = time.time()
    
    #messageテーブルに登録する。
    messagetable = dynamodb.Table('message')
    messagetable.put_item(
        Item  = {
            'id': nextseq,
            'message': response_data,
            'accepted_at': decimal.Decimal(str(now))
        }
    )

    # LINE Messaging APIに対するレスポンスを作成する
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + line_api_key}
    data = {'replyToken': reply_token,
        'messages': [
            {
                'type': 'text',
                'text': response_data
            }
        ]
    }
    
    # LINE Messaging APIにレスポンスを送信する
    response = requests.post('https://api.line.me/v2/bot/message/reply', headers=headers, data=json.dumps(data))

    # レスポンスのステータスコードをログに出力する
    print(response.status_code)
    
    # Lambda関数のレスポンスを返す
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'success'})
    }