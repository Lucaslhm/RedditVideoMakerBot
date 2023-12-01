async def clear_cookie_by_name(context, cookie_cleared_name):
    cookies = await context.cookies()
    filtered_cookies = [cookie for cookie in cookies if cookie["name"] != cookie_cleared_name]
    await context.clear_cookies()
    await context.add_cookies(filtered_cookies)
