from datetime import datetime
from typing import Any, List
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn
from rich.console import Console
from rich import print
from pydantic import BaseModel
import httpx
import asyncio
import sys


class Beatmap(BaseModel):
    difficulty_ar: float
    difficulty_hp: float
    source: str
    bpm: float
    play_length: int
    difficulty_od: float
    beatmapset: int
    favorites: int
    gamemode: int
    date: datetime
    mapper: str
    genre: str
    difficulty: float
    difficulty_cs: float
    difficulty_name: str
    pass_count: int
    beatmap_id: int
    artist: str
    beatmapset_id: int
    language: str
    total_length: int
    beatmap_status: int
    title: str
    map_count: int
    play_count: int
    ignored: Any


class QueryMaps(BaseModel):
    result_count: int
    beatmaps: List[Beatmap] = []

downloaded_count = 0
console = Console()
query_url = "https://osusearch.com/query/?statuses=Unranked&modes=Standard&min_length=90&star=(5.00,10.00)&premium_mappers=true&offset={}"
cookies: httpx.Cookies = None

def query_maps(offset=0):
    response = httpx.get(query_url.format(offset), timeout=httpx.Timeout(10.0))
    return QueryMaps(**response.json())


def login(username, password):
    osu_home = httpx.get("https://osu.ppy.sh/home")
    _token = osu_home.cookies.get("XSRF-TOKEN")
    payload = dict(
        _token=_token,
        username=username,
        password=password
    )
    headers = httpx.Headers()
    headers["origin"] = 'https://osu.ppy.sh'
    headers["referer"] = 'https://osu.ppy.sh/home'
    session = httpx.post("https://osu.ppy.sh/session", data=payload, cookies=osu_home.cookies, headers=headers)
    if session.is_error:
        print("登入失敗!")
        exit()

    global cookies
    cookies = session.cookies
    user_data = session.json()
    print(f"登入成功! {user_data['user']['username']}#{user_data['user']['id']}")

def fixedfilename(filename: str):
    return filename.replace('<', '_') \
        .replace('>', '_') \
        .replace('/', '_') \
        .replace('\\', '_') \
        .replace(':', '_') \
        .replace('*', '_') \
        .replace('?', '_') \
        .replace('"', '_') \
        .replace('|', '_')

async def download_map(client: httpx.AsyncClient, progress: Progress, save_path: str, setid):
    global cookies, downloaded_count
    headers = httpx.Headers()
    headers['Referer'] = 'https://osu.ppy.sh/'
    async with client.stream('GET', f"https://osu.ppy.sh/beatmapsets/{setid}/download", cookies=cookies, headers=headers, follow_redirects=True) as response:
        if response.status_code == 429:
            console.print("[red]429 Too Many Requests")
            raise Exception("429 Too Many Requests")
        elif response.status_code == 404:
            return

        total = int(response.headers["Content-Length"])
        filename = response.headers["Content-Disposition"].removeprefix("attachment;filename=\"").removesuffix("\";")
        filename = fixedfilename(filename)
        file = open(save_path+filename, 'wb')
        download_task = progress.add_task(filename, total=total)
        async for chunk in response.aiter_bytes():
            file.write(chunk)
            progress.update(download_task, completed=response.num_bytes_downloaded)
        file.close()
        progress.update(download_task, visible=False)
        progress.log(filename+" 下載完成!")
        downloaded_count += 1


def logout():
    global cookies
    headers = httpx.Headers()
    headers['Referer'] = 'https://osu.ppy.sh/'
    httpx.delete("https://osu.ppy.sh/session")

async def main(offset=0, *args):
    http_client = httpx.AsyncClient()
    running = True
    batch = 3

    if offset:
        console.print(f"{offset=}")
        offset = int(offset)

    username = input("Username: ")
    password = input("Password: ")
    path = input("請輸入存放位置: (預設為./)") or "./"
    login(username, password)

    with Progress(
        "[progress.percentage]{task.description}",
        BarColumn(),
        DownloadColumn(binary_units=True),
        TransferSpeedColumn()
    ) as progress:
        progress.log("開始進行下載程式...")

        try:
            while running:
                progress.log("正在獲取圖譜資訊...")
                maps_data = query_maps(offset)
                if maps_data.result_count > 0:
                    progress.log(f"總計找到 {maps_data.result_count} 張圖譜")

                for r in range(0, len(maps_data.beatmaps), batch):
                    await asyncio.gather(
                        *[download_map(http_client, progress, path, map.beatmapset_id) for map in maps_data.beatmaps[r:r+batch]]
                    )

                if len(maps_data.beatmaps):
                    offset += 1
                else:
                    console.log("已經沒有圖了!")
                    running = False
        except KeyboardInterrupt:
            console.print("等待http_client停止")
            await http_client.aclose()
            console.print("登出中...")
            console.logout()
        finally:
            return offset


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        offset = loop.run_until_complete(main(*sys.argv[1:]))
    except Exception as e:
        console.print_exception(show_locals=True)
        if cookies:
            console.print("登出中...")
            logout()
    console.print(f"程式已結束，總計下載 {downloaded_count} 張圖。")
    console.print(f"{offset=}")