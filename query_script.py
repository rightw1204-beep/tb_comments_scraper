import redis
import json

# Redis 连接配置
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    password='123456',
    decode_responses=True
)

while True:
    # 获取用户输入
    query_type = input("请输入查询类型 (all_key / all_id / item_id / item_id_page / quit): ")

    if query_type == "all_key":
        keys = redis_client.keys("*")
        for key in keys:
            value = redis_client.get(key)
            parsed_value = json.loads(value)
            print(f"键: {key}, 值: {parsed_value}")
    elif query_type == "all_id":
        value = redis_client.get("all_id")
        print(value)
        if value:
            item_ids = json.loads(value)
            next_query = input("是否继续查询? (item_id / item_id_page / 退出): ")
            if next_query == "item_id":
                item_id = input("请输入具体的 item_id : ")
                keys = redis_client.keys(f"*{item_id}*")
                for key in keys:
                    value = redis_client.get(key)
                    parsed_value = json.loads(value)
                    print(f"键: {key}, 值: {parsed_value}")
            elif next_query == "item_id_page":
                item_id = input("请输入具体的 item_id : ")
                page = input("请输入具体的 page 编号 : ")
                keys = redis_client.keys(f"{item_id}:{page}:*")
                for key in keys:
                    value = redis_client.get(key)
                    parsed_value = json.loads(value)
                    print(f"键: {key}, 值: {parsed_value}")
            elif next_query == "退出":
                break

    elif query_type == "quit":
        break
