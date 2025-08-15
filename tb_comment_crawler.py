import asyncio
import aiohttp
import hashlib
import json
import re
import random
import time
import redis
from DrissionPage import ChromiumPage, ChromiumOptions
from lxml import etree

# Redis 连接配置
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    password='123456',
    decode_responses=True
)

# 登录获取 cookies
page = ChromiumPage()
username = '15570010695'
password = 'wlj1204..'
page.get('https://login.taobao.com/havanaone/login/login.htm')
page.ele('xpath://*[@id="fm-login-id"]').clear().input(username)
page.ele('xpath://*[@id="fm-login-password"]').clear().input(password)
page.ele('xpath://*[@id="login-form"]/div[6]/button').click()
time.sleep(5)
cookies_list = page.cookies()
target_domain = '.taobao.com'
cookies = {cookie['name']: cookie['value'] for cookie in cookies_list if cookie['domain'] == target_domain}
page.quit()

headers = {
    'accept': '*/*',
    'accept-language': 'zh-CN,zh;q=0.9',
    'referer': 'https://detail.tmall.com/',
    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'script',
    'sec-fetch-mode': 'no-cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
}

appKey = "12574478"
em_data = '{"showTrueCount":false,"auctionNumId":"764774405362","pageNo":3,"pageSize":20,"rateType":"","searchImpr":"-8","orderType":"","expression":"","rateSrc":"pc_rate_list"}'


def get_sign(timestamp, appKey, em_data):
    token = cookies['_m_h5_tk'].split('_')[0]
    n_data = token + "&" + str(timestamp) + "&" + appKey + "&" + em_data
    return hashlib.md5(n_data.encode('utf-8')).hexdigest()


async def fetch_comments(session, item_id, page):
    timestamp = int(time.time() * 1000)
    new_em_data = em_data.replace('"pageNo":3', f'"pageNo":{page}').replace(
        '"auctionNumId":"764774405362"', f'"auctionNumId":"{item_id}"'
    )
    params = {
        'jsv': '2.7.4',
        'appKey': appKey,
        't': str(timestamp),
        'sign': get_sign(timestamp, appKey, new_em_data),
        'api': 'mtop.taobao.rate.detaillist.get',
        'v': '6.0',
        'isSec': '0',
        'ecode': '1',
        'timeout': '20000',
        'jsonpIncPrefix': 'pcdetail',
        'type': 'jsonp',
        'dataType': 'jsonp',
        'callback': 'mtopjsonppcdetail17',
        'data': new_em_data
    }

    async with session.get(
            'https://h5api.m.tmall.com/h5/mtop.taobao.rate.detaillist.get/6.0/',
            params=params,
            cookies=cookies,
            headers=headers
    ) as response:
        print(f"商品ID {item_id} 第{page}页响应状态码: {response.status}")
        text = await response.text()
        if "验证码" in text or "verify" in text.lower():
            print(f"商品ID {item_id} 第{page}页触发验证码，爬取暂停！请手动处理验证码，完成后输入 'continue' 继续爬取：")
            while input() != 'continue':
                print("请手动处理验证码，完成后输入 'continue'：")
            return
        res_str = re.findall(r'mtopjsonppcdetail[a-zA-Z0-9]+\((.*?)\)\s*$', text)[0]
        res = json.loads(res_str)
        rateList = res.get('data', {}).get('rateList', [])
        if not rateList:
            print(f"商品ID {item_id} 第{page}页无评论数据，跳过...")
            return
        comments = []
        for rate in rateList:
            comment = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', rate.get('feedback', ''))
            if comment:
                comment_hash = hashlib.md5(comment.encode('utf-8')).hexdigest()
                comment_data = {
                    'item_id': item_id,
                    'page': page,
                    'comment': comment
                }
                redis_client.set(f"{item_id}:{page}:{comment_hash}", json.dumps(comment_data))
                print(f"商品ID {item_id} 第{page}页评论存储到Redis: {comment}")
                comments.append(comment)
        return comments


async def scrape_item_comments(item_id, max_pages=3):
    async with aiohttp.ClientSession() as session:
        for page in range(1, max_pages + 1):
            print(f"正在获取商品ID {item_id} 第{page}页评论...")
            await fetch_comments(session, item_id, page)
            await asyncio.sleep(random.uniform(2, 4))


def scrape_taobao_item_ids(pages=3):
    options = ChromiumOptions()
    browser = ChromiumPage(options)
    id_list = []

    for page in range(1, pages + 1):
        url = f'https://s.taobao.com/search?_input_charset=utf-8&commend=all&ie=utf8&initiative_id=tbindexz_20170306&page={page}&preLoadOrigin=https%3A%2F%2Fwww.taobao.com&q=%E7%94%B5%E8%84%91&search_type=item&source=suggest&sourceId=tb.index&spm=a21bo.jianhua%2Fa.search_history.d1&ssid=s5-e&suggest_query=&tab=all&wq='
        browser.get(url)
        browser.wait.ele_displayed('//*[@id="content_items_wrapper"]', timeout=10)
        time.sleep(random.uniform(2, 3))

        HTML = browser.html
        etree_html = etree.HTML(HTML)
        shop_msg = etree_html.xpath('//*[@id="content_items_wrapper"]/div')
        for shop in shop_msg:
            num_id = shop.xpath('./a/@data-spm-act-id')
            if num_id and num_id[0].isdigit():
                id_list.append(num_id[0])

    browser.close()
    # 将 item_id 列表存储到 Redis，键名为 all_id
    redis_client.set('all_id', json.dumps(id_list))
    print(f"抓取到的商品ID列表已存储到 Redis!")
    return id_list


async def main():
    print("开始抓取淘宝商品ID...")
    item_ids = scrape_taobao_item_ids(pages=3)
    print(f"抓取到的商品ID: {item_ids}")

    for item_id in item_ids:
        print(f"开始抓取商品ID {item_id} 的评论...")
        await scrape_item_comments(item_id)


if __name__ == "__main__":
    asyncio.run(main())
