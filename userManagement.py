import json
import boto3
import jwt
import os
from datetime import datetime
from botocore.exceptions import ClientError

# 初始化 AWS 服务客户端
cognito = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb')

# 从环境变量获取配置（需在 Lambda 控制台设置）
USER_POOL_ID = os.environ.get('USER_POOL_ID')
CLIENT_ID = os.environ.get('CLIENT_ID')
# DynamoDB 表名（需提前创建，分别存储不同类型用户）
STUDENT_TABLE = 'StudentUser'
TEACHER_TABLE = 'TeacherUser'
ADMIN_TABLE = 'AdminUser'

def lambda_handler(event, context):
    print("收到请求:", event)  # 调试用
    
    # 解析请求方法和路径
    http_method = event.get('httpMethod')
    resource = event.get('resource')
    query_params = event.get('queryStringParameters', {})
    path_params = event.get('pathParameters', {})
    
    # 验证授权（从请求头获取 Token）
    auth_header = event.get('headers', {}).get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return {
            'statusCode': 401,
            'body': json.dumps({'message': '未提供有效认证令牌'})
        }
    token = auth_header.split(' ')[1]
    try:
        # 验证 Token（需替换为你的 Cognito 公钥或使用 SDK 验证）
        decoded = jwt.decode(token, options={"verify_verify_signature": True})  # 生产环境需验证签名
        current_user_groups = decoded.get('cognito:groups', [])
        if 'admin' not in current_user_groups:
            return {
                'statusCode': 403,
                'body': json.dumps({'message': '无管理员权限'})
            }
    except Exception as e:
        return {
            'statusCode': 401,
            'body': json.dumps({'message': f'令牌验证失败: {str(e)}'})
        }
    
    # 路由处理
    try:
        # 1. 查询用户列表（GET /admin/users）
        if http_method == 'GET' and resource == '/admin/users':
            user_type = query_params.get('userType', 'all')
            users = get_users(user_type)
            return {
                'statusCode': 200,
                'body': json.dumps({'users': users})
            }
        
        # 2. 创建用户（POST /admin/users）
        elif http_method == 'POST' and resource == '/admin/users':
            body = json.loads(event.get('body', '{}'))
            result = create_user(body)
            return {
                'statusCode': 200,
                'body': json.dumps({'message': result})
            }
        
        # 3. 修改用户（PUT /admin/users）
        elif http_method == 'PUT' and resource == '/admin/users':
            body = json.loads(event.get('body', '{}'))
            result = update_user(body)
            return {
                'statusCode': 200,
                'body': json.dumps({'message': result})
            }
        
        # 4. 删除用户（DELETE /admin/users）
        elif http_method == 'DELETE' and resource == '/admin/users':
            user_id = query_params.get('userId')
            user_type = query_params.get('userType')
            if not user_id or not user_type:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'message': '缺少用户ID或类型'})
                }
            result = delete_user(user_id, user_type)
            return {
                'statusCode': 200,
                'body': json.dumps({'message': result})
            }
        
        # 5. 查询单个用户（GET /admin/users/{userId}）
        elif http_method == 'GET' and resource == '/admin/users/{userId}':
            user_id = path_params.get('userId')
            user_type = query_params.get('userType')
            if not user_id or not user_type:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'message': '缺少用户ID或类型'})
                }
            user = get_user_detail(user_id, user_type)
            return {
                'statusCode': 200,
                'body': json.dumps({'user': user})
            }
        
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({'message': '接口不存在'})
            }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f'服务器错误: {str(e)}'})
        }


# ------------------------------
# 核心功能函数
# ------------------------------

def get_users(user_type):
    """查询用户列表（按类型筛选）"""
    users = []
    # 根据用户类型查询对应 DynamoDB 表
    if user_type == 'student' or user_type == 'all':
        table = dynamodb.Table(STUDENT_TABLE)
        response = table.scan()
        users.extend([{
            'userId': item['userId'],
            'username': item['username'],
            'email': item['email'],
            'userType': 'student',
            'grade': item.get('grade', ''),
            'createTime': item['createTime']
        } for item in response.get('Items', [])])
    
    if user_type == 'teacher' or user_type == 'all':
        table = dynamodb.Table(TEACHER_TABLE)
        response = table.scan()
        users.extend([{
            'userId': item['userId'],
            'username': item['username'],
            'email': item['email'],
            'userType': 'teacher',
            'subject': item.get('subject', ''),
            'createTime': item['createTime']
        } for item in response.get('Items', [])])
    
    if user_type == 'admin' or user_type == 'all':
        table = dynamodb.Table(ADMIN_TABLE)
        response = table.scan()
        users.extend([{
            'userId': item['userId'],
            'username': item['username'],
            'email': item['email'],
            'userType': 'admin',
            'permission': item.get('permission', 'full'),
            'createTime': item['createTime']
        } for item in response.get('Items', [])])
    
    return users


def get_user_detail(user_id, user_type):
    """查询单个用户详情"""
    table_name = {
        'student': STUDENT_TABLE,
        'teacher': TEACHER_TABLE,
        'admin': ADMIN_TABLE
    }.get(user_type)
    if not table_name:
        raise ValueError('无效的用户类型')
    
    table = dynamodb.Table(table_name)
    response = table.get_item(Key={'userId': user_id})
    item = response.get('Item')
    if not item:
        raise ValueError(f'用户 {user_id} 不存在')
    return item


def create_user(user_data):
    """创建用户（同步到 Cognito 和 DynamoDB）"""
    user_type = user_data.get('userType')
    user_id = user_data.get('userId')
    username = user_data.get('username')
    password = user_data.get('password')
    email = user_data.get('email')
    
    # 1. 验证必填字段
    if not all([user_type, user_id, username, password, email]):
        raise ValueError('缺少必填字段')
    
    # 2. 在 Cognito 中创建用户
    try:
        cognito.sign_up(
            ClientId=CLIENT_ID,
            Username=username,
            Password=password,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'custom:userId', 'Value': user_id},  # 自定义字段存储用户ID
                {'Name': 'custom:userType', 'Value': user_type}
            ]
        )
        # 自动确认用户（无需邮箱验证）
        cognito.admin_confirm_sign_up(
            UserPoolId=USER_POOL_ID,
            Username=username
        )
        # 添加用户到对应组（如 admin 组）
        cognito.admin_add_user_to_group(
            UserPoolId=USER_POOL_ID,
            Username=username,
            GroupName=user_type
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'UsernameExistsException':
            raise ValueError('用户名已存在')
        else:
            raise ValueError(f'Cognito 创建失败: {e.response["Error"]["Message"]}')
    
    # 3. 存储到 DynamoDB
    table_name = {
        'student': STUDENT_TABLE,
        'teacher': TEACHER_TABLE,
        'admin': ADMIN_TABLE
    }.get(user_type)
    if not table_name:
        raise ValueError('无效的用户类型')
    
    table = dynamodb.Table(table_name)
    item = {
        'userId': user_id,
        'username': username,
        'email': email,
        'userType': user_type,
        'createTime': datetime.utcnow().isoformat()
    }
    # 添加扩展字段
    if user_type == 'student':
        item['grade'] = user_data.get('grade', '')
    elif user_type == 'teacher':
        item['subject'] = user_data.get('subject', '')
    elif user_type == 'admin':
        item['permission'] = user_data.get('permission', 'full')
    
    table.put_item(Item=item)
    return f'{user_type} 用户创建成功'


def update_user(user_data):
    """修改用户信息"""
    user_id = user_data.get('userId')
    user_type = user_data.get('userType')
    username = user_data.get('username')
    email = user_data.get('email')
    new_password = user_data.get('password')  # 可选，不填则不修改
    
    if not all([user_id, user_type, username, email]):
        raise ValueError('缺少必填字段')
    
    # 1. 更新 Cognito 用户信息
    try:
        # 更新邮箱和用户名
        cognito.admin_update_user_attributes(
            UserPoolId=USER_POOL_ID,
            Username=username,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'preferred_username', 'Value': username}
            ]
        )
        # 若提供新密码，则更新
        if new_password:
            cognito.admin_set_user_password(
                UserPoolId=USER_POOL_ID,
                Username=username,
                Password=new_password,
                Permanent=True
            )
    except ClientError as e:
        raise ValueError(f'Cognito 更新失败: {e.response["Error"]["Message"]}')
    
    # 2. 更新 DynamoDB
    table_name = {
        'student': STUDENT_TABLE,
        'teacher': TEACHER_TABLE,
        'admin': ADMIN_TABLE
    }.get(user_type)
    if not table_name:
        raise ValueError('无效的用户类型')
    
    table = dynamodb.Table(table_name)
    update_expr = 'set username = :u, email = :e'
    expr_attr = {':u': username, ':e': email}
    
    # 扩展字段更新
    if user_type == 'student' and 'grade' in user_data:
        update_expr += ', grade = :g'
        expr_attr[':g'] = user_data['grade']
    elif user_type == 'teacher' and 'subject' in user_data:
        update_expr += ', subject = :s'
        expr_attr[':s'] = user_data['subject']
    elif user_type == 'admin' and 'permission' in user_data:
        update_expr += ', permission = :p'
        expr_attr[':p'] = user_data['permission']
    
    table.update_item(
        Key={'userId': user_id},
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expr_attr
    )
    return f'{user_type} 用户更新成功'


def delete_user(user_id, user_type):
    """删除用户（同步删除 Cognito 和 DynamoDB 数据）"""
    # 1. 查询用户获取 username（用于删除 Cognito 用户）
    table_name = {
        'student': STUDENT_TABLE,
        'teacher': TEACHER_TABLE,
        'admin': ADMIN_TABLE
    }.get(user_type)
    if not table_name:
        raise ValueError('无效的用户类型')
    
    table = dynamodb.Table(table_name)
    response = table.get_item(Key={'userId': user_id})
    item = response.get('Item')
    if not item:
        raise ValueError(f'用户 {user_id} 不存在')
    username = item['username']
    
    # 2. 从 Cognito 中删除用户
    try:
        cognito.admin_delete_user(
            UserPoolId=USER_POOL_ID,
            Username=username
        )
    except ClientError as e:
        raise ValueError(f'Cognito 删除失败: {e.response["Error"]["Message"]}')
    
    # 3. 从 DynamoDB 中删除用户
    table.delete_item(Key={'userId': user_id})
    return f'{user_type} 用户删除成功'