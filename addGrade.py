import boto3
import json 
from datetime import datetime,timedelta
import os

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
grade_table = dynamodb.Table('Grade')  # 初始化表，变量名为grade_table

def handle_add_grade(event):
    try:
        body = json.loads(event['body'])
        
        # 验证必填字段
        required_fields = ['id', 'studentId', 'course', 'score', 'semester']
        for field in required_fields:
            if field not in body:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'message': f'缺少必填字段：{field}'})
                }
        
        # 验证分数范围
        if not (0 <= body['score'] <= 100):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': '分数必须在0-100之间'})
            }
        
        # 写入DynamoDB时，使用初始化的grade_table变量
        grade_table.put_item(Item={
            'gradeId': body['id'],  # 主键：gradeId
            'studentId': body['studentId'],
            'course': body['course'],
            'score': body['score'],
            'semester': body['semester'],
            'createTime': body.get('createTime', (datetime.utcnow() + timedelta(hours=8)).isoformat()),
            'updateTime': body.get('createTime', (datetime.utcnow() + timedelta(hours=8)).isoformat())
        })
        
        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': '成绩添加成功',
                'gradeId': body['id']  # 返回生成的gradeId
            })
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f'添加失败：{str(e)}'})
        }

def lambda_handler(event, context):
    http_method = event['httpMethod']
    path = event['path']
    
    # 处理添加成绩（POST /grades）
    if http_method == 'POST' and path == '/grades':
        return handle_add_grade(event)
    # 其他路由（查询、修改、删除）可在此处补充
    else:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': '接口不存在'})
        }