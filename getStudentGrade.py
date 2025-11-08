import boto3
import json
from decimal import Decimal
from datetime import datetime, timedelta  # 导入timedelta处理时区

# 初始化 DynamoDB 资源
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
grade_table = dynamodb.Table('Grade')
query_time_table = dynamodb.Table('QueryTimeConfig')  # 新增查询时间表

def safe_parse_iso_time(time_str):
    try:
        # 尝试解析带时区的格式（如 2025-10-31T10:50:00+08:00）
        return datetime.fromisoformat(time_str)
    except ValueError:
        # 若失败，尝试解析不带时区的格式（如 2025-10-31T10:50:00）
        return datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S")

def lambda_handler(event, context):
    try:
        # 1. 获取并校验 studentId
        query_params = event.get('queryStringParameters', {})
        student_id = query_params.get('studentId', '').strip()
        print(f"前端传递的 studentId：{student_id}")
        if not student_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com',
                    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                },
                'body': json.dumps({'message': '缺少 studentId 参数（学号）'})
            }

        # 2. 从 QueryTimeConfig 表中查询全局查询时间
        time_config = query_time_table.get_item(
            Key={'configKey': 'globalQueryTime'}
        ).get('Item', {})
        query_start_time = time_config.get('queryStartTime', '')
        query_end_time = time_config.get('queryEndTime', '')
        print(f"获取的查询时间范围：{query_start_time} 至 {query_end_time}")
        
        # 校验查询时间是否配置
        if not query_start_time or not query_end_time:
            return {
                'statusCode': 403,
                'headers': {
                    'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com',
                    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                },
                'body': json.dumps({'message': '教师未配置查询时间，请联系教师设置'})
            }

        # 3. 转换为北京时间后校验（UTC+8）
        now = datetime.utcnow() + timedelta(hours=8)  # 转换为北京时间
        start = safe_parse_iso_time(query_start_time)
        end = safe_parse_iso_time(query_end_time)
        if not (start <= now <= end):
            return {
                'statusCode': 403,
                'headers': {
                    'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com',
                    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                },
                'body': json.dumps({
                    'message': '当前不在可查询时间区间内',
                    'queryTimeRange': f"{query_start_time} 至 {query_end_time}",
                    'currentBeijingTime': now.isoformat()  # 调试用：返回当前北京时间
                })
            }

        # 4. 基于 studentId 筛选成绩
        response = grade_table.scan(
            FilterExpression='studentId = :sid',
            ExpressionAttributeValues={':sid': student_id}
        )
        grades = response.get('Items', [])
        print(f"查询到的原始成绩数据：{grades}")

        # 5. 格式化成绩并注入查询时间
        formatted_grades = []
        for grade in grades:
            score = int(grade['score']) if isinstance(grade['score'], Decimal) else grade.get('score', 0)
            formatted_grades.append({
                'course': grade.get('course', ''),
                'score': score,
                'semester': grade.get('semester', ''),
                'updateTime': grade.get('updateTime', ''),
                'queryStartTime': query_start_time,
                'queryEndTime': query_end_time
            })

        # 6. 返回结果
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps({
                'studentId': student_id,
                'gradeCount': len(formatted_grades),
                'grades': formatted_grades,
                'queryTimeRange': f"{query_start_time} 至 {query_end_time}"
            })
        }

    except Exception as e:
        print(f"查询失败，异常信息：{str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps({'message': f'查询失败：{str(e)}'})
        }