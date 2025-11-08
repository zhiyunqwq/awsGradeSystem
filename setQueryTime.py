import boto3
import json
from datetime import datetime

# 初始化 DynamoDB 资源
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
grade_table = dynamodb.Table('Grade')
query_time_table = dynamodb.Table('QueryTimeConfig')  # 新增查询时间表

def lambda_handler(event, context):
    http_method = event['httpMethod']
    path = event['path']
    
    # 1. 设置查询时间段：POST /query-time
    if http_method == 'POST' and path == '/query-time':
        return handle_set_query_time(event)
    
    # 2. 查询当前查询时间段：GET /query-time
    elif http_method == 'GET' and path == '/query-time':
        return handle_get_query_time()
    
    # 其他接口（成绩查询、修改、删除）...
    else:
        return {
            'statusCode': 404,
            'headers': {'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'},
            'body': json.dumps({'message': '接口不存在'})
        }

# 设置查询时间段（教师操作）
def handle_set_query_time(event):
    try:
        body = json.loads(event['body'])
        config_key = body.get('configKey', 'globalQueryTime')  # 默认为全局配置
        start_time = body.get('queryStartTime')
        end_time = body.get('queryEndTime')
        
        # 验证时间格式（可选，示例用字符串直接存储）
        if not start_time or not end_time:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'},
                'body': json.dumps({'message': '请填写开始时间和结束时间'})
            }
        
        # 写入查询时间表
        query_time_table.put_item(
            Item={
                'configKey': config_key,
                'queryStartTime': start_time,
                'queryEndTime': end_time,
                'updateTime': datetime.utcnow().isoformat()
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'},
            'body': json.dumps({
                'message': '查询时间段设置成功',
                'configKey': config_key,
                'queryStartTime': start_time,
                'queryEndTime': end_time
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'},
            'body': json.dumps({'message': f'设置失败：{str(e)}'})
        }

# 查询当前查询时间段
def handle_get_query_time():
    try:
        response = query_time_table.get_item(
            Key={'configKey': 'globalQueryTime'}
        )
        config = response.get('Item', {})
        
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'},
            'body': json.dumps({
                'queryStartTime': config.get('queryStartTime', '未设置'),
                'queryEndTime': config.get('queryEndTime', '未设置'),
                'updateTime': config.get('updateTime', '未设置')
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'},
            'body': json.dumps({'message': f'查询失败：{str(e)}'})
        }