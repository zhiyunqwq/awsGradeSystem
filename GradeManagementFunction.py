import boto3
import json
from datetime import datetime
import os
import json
from decimal import Decimal

# 自定义 JSON 编码器，处理 Decimal 类型
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o)  # 转换为整数
        return super(DecimalEncoder, self).default(o)

# 初始化 DynamoDB 客户端
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_NAME', 'Grade')  # 从环境变量获取表名，默认StudentGrades
table = dynamodb.Table(table_name)

def lambda_handler(event, context):
    # 解析请求方法和路径
    http_method = event['httpMethod']
    path = event['path']
    
    # 1. 查询成绩：GET /grades
    if http_method == 'GET' and path == '/gradesTeacher':
        return handle_query_grades(event)
    
    # 2. 修改成绩：PUT /grades/{id}
    elif http_method == 'PUT' and path.startswith('/gradesTeacher/'):
        grade_id = path.split('/')[-1]  # 提取路径中的成绩ID
        return handle_update_grade(event, grade_id)
    
    # 3. 删除成绩：DELETE /grades/{id}
    elif http_method == 'DELETE' and path.startswith('/gradesTeacher/'):
        grade_id = path.split('/')[-1]
        return handle_delete_grade(grade_id)
    
    # 无效请求
    else:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': '接口不存在'})
        }

# 处理教师查询成绩（支持按学号筛选）
def handle_query_grades(event):
    try:
        # 获取查询参数（教师可通过学号查询）
        query_params = event.get('queryStringParameters', {})
        student_id = query_params.get('studentId')  # 教师输入的学号
        
        # 构建筛选条件
        filter_expressions = []
        expression_attrs = {}
        
        if student_id:
            filter_expressions.append('studentId = :s')
            expression_attrs[':s'] = student_id
        
        # 执行扫描
        scan_kwargs = {}
        if filter_expressions:
            scan_kwargs['FilterExpression'] = ' AND '.join(filter_expressions)
            scan_kwargs['ExpressionAttributeValues'] = expression_attrs
        
        response = table.scan(** scan_kwargs)
        grades = response.get('Items', [])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'
            },
            'body': json.dumps({'grades': grades}, cls=DecimalEncoder) # 返回包含gradeId（id）的完整数据
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'
            },
            'body': json.dumps({'message': f'查询失败：{str(e)}'})
        }

# 处理教师修改成绩（通过gradeId定位记录）
def handle_update_grade(event, grade_id):
    try:
        body = json.loads(event['body'])
        new_score = body.get('score')
        
        # 验证分数
        if new_score is None or not (0 <= new_score <= 100):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'
                },
                'body': json.dumps({'message': '分数必须在0-100之间'})
            }
        
        # 执行更新
        update_response = table.update_item(
            Key={'gradeId': grade_id},
            UpdateExpression='SET score = :score, updateTime = :time',
            ExpressionAttributeValues={
                ':score': new_score,
                ':time': datetime.utcnow().isoformat()
            },
            ReturnValues='ALL_NEW'
        )
        
        # 3. 返回结果时使用自定义编码器，处理Decimal
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'
            },
            'body': json.dumps({
                'message': '成绩修改成功',
                'updatedGrade': update_response['Attributes']
            }, cls=DecimalEncoder)  
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'
            },
            'body': json.dumps({'message': f'修改失败：{str(e)}'}, cls=DecimalEncoder)
        }

# 处理教师删除成绩（通过gradeId删除）
def handle_delete_grade(grade_id):
    try:
        # 删除记录（主键为id，即gradeId）
        table.delete_item(Key={'gradeId': grade_id})
        print(f"删除成功，gradeId：{grade_id}")  # 修复原代码中引用未定义event的错误
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'
            },
            'body': json.dumps({'message': f'成绩记录（gradeId：{grade_id}）删除成功'})
        }
    
    except table.meta.client.exceptions.ResourceNotFoundException:
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'
            },
            'body': json.dumps({'message': f'成绩记录不存在（gradeId：{grade_id}）'})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'http://grade111.s3-website.us-east-2.amazonaws.com'
            },
            'body': json.dumps({'message': f'删除失败：{str(e)}'})
        }