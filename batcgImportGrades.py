import boto3
import json
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import re
import base64
from decimal import Decimal  # 导入Decimal

# 初始化 DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
grade_table = dynamodb.Table('Grade')

def lambda_handler(event, context):
    try:
        # 解析请求中的文件
        if 'body' not in event or not event['body']:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': '未收到文件'})
            }
        file_content = base64.b64decode(event['body'])
        file_name = event.get('headers', {}).get('X-File-Name', 'unknown.xlsx')
        file_ext = file_name.split('.')[-1].lower()

        # 读取并解析文件
        df = None
        try:
            if file_ext in ['xlsx', 'xls']:
                df = pd.read_excel(BytesIO(file_content), engine='openpyxl')
            elif file_ext == 'csv':
                df = pd.read_csv(BytesIO(file_content))
            else:
                return {
                    'statusCode': 400,
                    'headers': {'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'message': '不支持的文件格式'})
                }
        except Exception as e:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': f'文件解析失败：{str(e)}'})
            }

        # 验证表头
        required_cols = ['studentId', 'course', 'score', 'semester']
        if not all(col in df.columns for col in required_cols):
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': '文件表头缺失，需包含：studentId, course, score, semester',
                    'found_cols': list(df.columns)
                })
            }

        # 处理每条数据
        success_count = 0
        failure_count = 0
        failures = []
        beijing_time = datetime.utcnow() + timedelta(hours=8)

        for _, row in df.iterrows():
            try:
                student_id = str(row['studentId']).strip()
                course = str(row['course']).strip()
                # 分数转换为Decimal类型
                score = Decimal(str(row['score']))
                semester = str(row['semester']).strip()

                if not (0 <= score <= 100):
                    raise ValueError('分数必须在0-100之间')

                clean_course = re.sub(r'[^a-zA-Z0-9]', "", course)
                grade_id = f"{student_id}_{clean_course}_{beijing_time.timestamp()}"

                grade_table.put_item(Item={
                    'gradeId': grade_id,
                    'studentId': student_id,
                    'course': course,
                    'score': score,
                    'semester': semester,
                    'createTime': beijing_time.isoformat(),
                    'updateTime': beijing_time.isoformat()
                })
                success_count += 1
            except Exception as e:
                failure_count += 1
                failures.append({
                    'row': row.to_dict(),
                    'error': str(e)
                })

        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'successCount': success_count,
                'failureCount': failure_count,
                'failures': failures
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f'批量导入失败：{str(e)}'})
        }