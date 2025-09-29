from django.shortcuts import render, get_object_or_404,redirect
import requests
from django.http import JsonResponse,HttpResponseRedirect
from .models import BitcoinPrice,UserProfile,Coin,CoinHistory,User,FeedbackQuestion,FeedbackAnswer,PageTracker
from datetime import datetime, timedelta
from django.core.paginator import Paginator
# 登入頁面
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import UserProfileForm
from PIL import Image
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from io import BytesIO
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.utils.safestring import mark_safe
import plotly.graph_objects as go
from django.templatetags.static import static
from django.utils.timezone import now
import re
import pandas as pd
from decimal import Decimal
import ta
from pathlib import Path
from dotenv import load_dotenv

import os
import numpy as np

env_path = Path(__file__).resolve().parents[2] / '.env'

# 加載 .env 檔案
load_dotenv(dotenv_path=env_path)

api = os.getenv('OPEN_API')

def home(request):
    try:
        today = timezone.now().date()

        sign_in_record = None
        progress_percentage = 0

        if request.user.is_authenticated:
            user = request.user
            sign_in_record = SignIn.objects.filter(user=user).first()

            if sign_in_record:
                progress_days = sign_in_record.consecutive_sign_in_count % 7
                progress_percentage = int((progress_days / 7) * 100)

                if progress_days == 0 and sign_in_record.consecutive_sign_in_count > 0:
                    progress_percentage = 100

        # 資料查詢
        top_coins = BitcoinPrice.objects.all().order_by('id')[:5]
        increase_coins = BitcoinPrice.objects.all().order_by('-change_24h')[:5]
        decline_coins = BitcoinPrice.objects.all().order_by('change_24h')[:5]
        volume = BitcoinPrice.objects.all().order_by('-volume_24h')[:5]
        image_url = request.build_absolute_uri(static('images/crypto.png')) 
        
        return render(request, 'home.html', {
            'top_coins': top_coins,
            'increase_coins': increase_coins,
            'decline_coins': decline_coins,
            'volume': volume,
            'image_url': image_url,
            'sign_in_record': sign_in_record,
            'today': today,
            'progress_percentage': progress_percentage,
        })

    except Exception as e:
        print(f"錯誤: {e}")
        return render(request, 'home.html', {
            'error': '無法獲取資料，請稍後再試。'
        })


#註冊
from django.db import IntegrityError
def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        email = request.POST['email']
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')

        # 檢查用戶名是否已經存在
        if User.objects.filter(username=username).exists():
            messages.error(request, '這個用戶名已經被使用')
            return render(request, 'register.html')

        # 檢查郵箱是否已經註冊
        if User.objects.filter(email=email).exists():
            messages.error(request, '這個email已經被使用')
            return render(request, 'register.html')

        try:
            # 使用 create_user 方法創建用戶，自動加密密碼
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            # 註冊成功後返回註冊頁面以顯示彈跳頁面
            messages.success(request, '您的帳戶已創建成功！請登入。')
            return render(request, 'register.html')

        except IntegrityError:
            messages.error(request, '用戶名或郵箱已存在，請選擇其他值')
            return render(request, 'register.html')
        except Exception as e:
            messages.error(request, f'創建用戶時發生錯誤：{e}')
            return render(request, 'register.html')

    return render(request, 'register.html')

    


# 登入頁面
def login_view(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')  # 登入成功後跳轉到首頁
        else:
            return render(request, 'login.html', {'error': '使用者名稱或密碼錯誤，請重新輸入一次'})
    return render(request, 'login.html')

# 登出功能
def logout_view(request):
    logout(request)
    return redirect('home')  # 登出後跳轉到登入頁

from django.db.models import F
from django.core.paginator import Paginator
from django.shortcuts import render

def format_crypto_price(value):
    """格式化虛擬貨幣價格，根據數值大小顯示適當的小數位數，並加上千分位符號"""
    try:
        value = float(value)
        if value == 0:
            return "0.00"
        elif value >= 1:
            # 大於等於 1：顯示最多 3 位小數，然後加上千分位符號
            formatted = f"{value:,.3f}".rstrip("0").rstrip(".")
            return formatted
        else:
            # 小於 1：找第一個非零後的兩位小數（最多 10 位精度）
            str_value = f"{value:.10f}"
            decimal_part = str_value.split('.')[1]
            non_zero_index = next((i for i, digit in enumerate(decimal_part) if digit != '0'), len(decimal_part))
            end_index = non_zero_index + 3  # 非零數字 + 後兩位小數
            formatted_decimal = decimal_part[:end_index].rstrip("0").rstrip(".")
            return f"0.{formatted_decimal}"
    except (ValueError, TypeError):
        return str(value)


def crypto_list(request):
    query = request.GET.get('query', '') 
    sort_by = request.GET.get('sort_by')  # 排序欄位
    sort_order = request.GET.get('sort_order')  # 排序狀態（"asc", "desc", "default"）

    if query:
        all_prices = BitcoinPrice.objects.filter(coin__coinname__icontains=query)
    else:
        all_prices = BitcoinPrice.objects.all()

    # 根據排序狀態進行排序
    if sort_by and sort_order == 'asc':
        all_prices = all_prices.order_by(sort_by)  # A-Z 排序
    elif sort_by and sort_order == 'desc':
        all_prices = all_prices.order_by(F(sort_by).desc())  # Z-A 排序
    else:
        # 預設根據 market_cap 由大到小排序
        all_prices = all_prices.order_by('-market_cap')

    paginator = Paginator(all_prices, 40)  # 每頁顯示10條數據
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 格式化價格數據
    for price in page_obj.object_list:
        price.usd_display = format_crypto_price(price.usd)
        price.twd_display = format_crypto_price(price.twd)
        price.jpy_display = format_crypto_price(price.jpy)
        price.eur_display = format_crypto_price(price.eur)
        price.volume_24h_display = format_crypto_price(price.volume_24h)
        price.market_cap_display = format_crypto_price(price.market_cap)

    if request.user.is_authenticated:
        user_profile = request.user.profile
        favorite_coin_ids = list(user_profile.favorite_coin.values_list('id', flat=True))
    else:
        favorite_coin_ids = []

    return render(request, 'crypto_list.html', {
        'page_obj': page_obj,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'favorite_coin_ids': favorite_coin_ids,
    })

def crypto_prices_ajax(request):
    query = request.GET.get('query', '') 
    sort_by = request.GET.get('sort_by')  
    sort_order = request.GET.get('sort_order')

    if query:
        prices = BitcoinPrice.objects.filter(coin__coinname__icontains=query)
    else:
        prices = BitcoinPrice.objects.all()

    if sort_by and sort_order == 'asc':
        prices = prices.order_by(sort_by)
    elif sort_by and sort_order == 'desc':
        prices = prices.order_by(F(sort_by).desc())
    else:
        prices = prices.order_by('-market_cap')

    # 只取前40筆，避免一次回傳太多資料
    prices = prices.all()

    # 準備回傳的資料格式
    data = []
    for price in prices:
        data.append({
            'id': price.id,
            'coin_name': price.coin.coinname,
            'usd': format_crypto_price(price.usd),
            'twd': format_crypto_price(price.twd),
            'jpy': format_crypto_price(price.jpy),
            'eur': format_crypto_price(price.eur),
            'volume_24h': format_crypto_price(price.volume_24h),
            'market_cap': format_crypto_price(price.market_cap),
        })

    return JsonResponse({'prices': data,'sort_by': sort_by,'sort_order': sort_order,})

from django.shortcuts import render, redirect
from .forms import UserProfileForm
from django.contrib.auth.decorators import login_required

@login_required
def upload_profile_image(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            # 取得上傳的圖片
            image = request.FILES.get('profile_image')

            # 如果有圖片上傳，進行處理
            if image:
                # 使用 Pillow 處理圖片
                img = Image.open(image)

                # 將圖片轉換為 RGB 格式，並保存為 JPG
                img = img.convert('RGB')

                # 設定最大寬度與高度（可根據需要調整）
                max_width = 500
                max_height = 500
                img.thumbnail((max_width, max_height))

                # 保存為 JPG 格式
                image_io = BytesIO()
                img.save(image_io, format='JPEG')
                image_io.seek(0)

                # 將處理過的圖片轉為 Django 可以儲存的 ContentFile
                image_name = f"{image.name.split('.')[0]}.jpg"  # 保留原檔名，但轉為 .jpg
                user_profile_image = ContentFile(image_io.read(), name=image_name)

                # 更新用戶檔案中的圖片
                request.user.profile.profile_image.save(image_name, user_profile_image)

            # 提交表單後，跳轉到主頁
            return redirect('user_profile')  # 或者你可以跳轉到其他頁面
    else:
        form = UserProfileForm(instance=request.user.profile)

    return render(request, 'user_profile.html', {'form': form})

@login_required
def add_to_favorites(request, pk):
    user_profile = request.user.profile
    try:
        crypto = Coin.objects.get(id=pk)
        user_profile.favorite_coin.add(crypto)
        user_profile.save()
        return JsonResponse({'status': 'success', 'action': 'add'})
    except Coin.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Coin not found'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def remove_from_favorites(request, pk):
    user_profile = request.user.profile
    coin = get_object_or_404(Coin, id=pk)

    # 移除最愛
    user_profile.favorite_coin.remove(coin)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})

    return redirect('favorite_coins')  # 如果不是 AJAX 請求，重定向回我的最愛頁面

@login_required
def favorite_coins(request):
    user_profile = request.user.profile
    favorite_cryptos = user_profile.favorite_coin.all()  # 獲取用戶的最愛幣
    return render(request, 'favorite_coins.html', {'favorite_cryptos': favorite_cryptos})

#忘記密碼
# from django.contrib.auth import views as auth_views
# from django.urls import reverse_lazy
# from django.contrib.auth import get_user_model

# class CustomPasswordResetView(auth_views.PasswordResetView):
#     template_name = 'password_reset_form.html'  # 忘記密碼表單
#     email_template_name = 'password_reset_email.html'  # 發送郵件的模板
#     success_url = reverse_lazy('password_reset_done')  # 成功後跳轉到 `password_reset_done`

# class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
#     template_name = 'password_reset_done.html'  # 提示郵件已發送的頁面

# class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
#     template_name = 'password_reset_confirm.html'  # 用戶輸入新密碼的頁面
#     success_url = reverse_lazy('password_reset_complete')  # 成功設置新密碼後跳轉的頁面

# class CustomPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
#     template_name = 'password_reset_complete.html'  # 密碼重設完成後的頁面

#重設密碼
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from django.shortcuts import render, redirect
from django.contrib import messages 

@login_required
def update_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('password')
        confirm_password = request.POST.get('password_confirm')

        user = request.user

        if not check_password(current_password, user.password):
            messages.error(request, '目前密碼不正確。', extra_tags='password')
            return redirect('user_profile')

        if new_password != confirm_password:
            messages.error(request, '新密碼與確認密碼不一致。', extra_tags='password')
            return redirect('user_profile')

        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)

        messages.success(request, '密碼已成功修改。', extra_tags='password')
        return redirect('user_profile')

    return render(request, 'user_profile.html')

@login_required
def update_firstname(request):
    if request.method == 'POST':
        new_firstname = request.POST.get('firstname')

        user = request.user

        if not new_firstname.strip():
            messages.error(request, '名稱不可為空。', extra_tags='firstname')
            return redirect('user_profile')  # 替換為你的對應路由名稱

        user.first_name = new_firstname
        user.save()

        messages.success(request, '名稱已成功修改。', extra_tags='firstname')
        return redirect('user_profile')  # 替換為你的對應路由名稱

    # GET 請求時返回對應的頁面
    return render(request, 'user_profile.html')



# 新聞推送
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import UserNotificationPreference


@login_required
def update_notification_preferences(request):
    # 設置更新通知的邏輯
    if request.method == 'POST':
        news_notifications = request.POST.get('news_notifications') == 'on'
        email_notifications = request.POST.get('email_notifications') == 'on'
        site_notifications = request.POST.get('site_notifications') == 'on'

        preference, created = UserNotificationPreference.objects.get_or_create(user=request.user)
        preference.news_notifications = news_notifications
        preference.email_notifications = email_notifications
        preference.site_notifications = site_notifications
        preference.save()

        messages.success(request, '通知設定已更新！')
        return redirect('user_profile')  # 更新後返回用戶設定頁面

    return redirect('user_profile')  # 如果不是 POST 請求，則重定向回首頁或其他頁面


from django.template.loader import render_to_string
from django.http import HttpResponse
from django.core.mail import send_mail

def send_email_news(request):
    # 获取所有用户
    users = User.objects.all()
    users = User.objects.filter(notification_preference__email_notifications=True)    
    if not users.exists():
    # 查詢結果不為空，執行某些操作
        return HttpResponse("Hello, world!")
    
    latest_articles = NewsArticle.objects.all().order_by('-time')[:1000]


    # 遍历所有用户并发送邮件
    for user in users:
        subject = '新聞通知'
        

        # 使用模板渲染 HTML 邮件内容
        html_content = render_to_string('email_template.html', {
            'subject': subject,
            'name': user.username,  # 假设你希望使用用户名来定制邮件内容
            'latest_articles':latest_articles,
        })

        # 使用 send_mail 发送邮件
        send_mail(
            subject,              # 邮件主题
            "",              # 邮件文本内容
            None, # 发件人邮箱，或者可以从 settings.py 获取
            [user.email],         # 收件人邮箱（每个用户的邮箱）
            html_message=html_content,  # 设置 HTML 内容
        )

    return render(request, 'email_template.html', {'subject':subject,'latest_articles': latest_articles,'name': user.username})

'''
import numpy as np
import pandas as pd
from data_analysis.prediction.btc import predict_crypto_price
import json
def crypto_price_chart(request):
    coin = Coin.objects.get(coinname="Bitcoin")
    recent_data = (
        CoinHistory.objects.filter(coin=coin)
        .order_by("-date")[:24]  # 取最近 24 小時
        .values("date", "close_price", "high_price", "low_price", "open_price", "volume")
    )

    # 轉換為 DataFrame
    df = pd.DataFrame(list(recent_data))
    df = df.sort_values("date")  # 依時間排序

    # 確保 date 欄位是 datetime 類型
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")  # 依時間排序
    # 預測價格
    predicted_price = predict_crypto_price(df[["close_price", "high_price", "low_price", "open_price", "volume"]])
    print(df["date"].iloc[-1] + pd.Timedelta(hours=1))
    # 構造 JSON 返回給前端
    data = {
        "labels": df["date"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist() + [(df["date"].iloc[-1] + pd.Timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")],  # 加入預測時間
        "prices": df["close_price"].tolist(),  # 歷史價格
        "predicted_price": {"date": df["date"].iloc[-1] + pd.Timedelta(hours=1), "price": predicted_price},
    }


    return render(request, "chart.html", {"chart_data": json.dumps(data , default=str)})
'''
def crypto_price_chart(request):
    return HttpResponse("hello")


def crypto_detail(request, coin_id):
    coin = get_object_or_404(Coin, id=coin_id)

    # 最新價格資料
    latest_price = BitcoinPrice.objects.filter(coin=coin).order_by('-timestamp').first()

    # 最新歷史資料（K 線）
    latest_history = CoinHistory.objects.filter(coin=coin).order_by('-date').first()

    return render(request, 'crypto_detail.html', {
        'coin_id': coin_id,
        'data': coin,  # 原本叫 data 的其實是 coin
        'coin': coin,  # 提供給 include 用
        'latest_price': latest_price,
        'latest_history': latest_history
    })

from django.db.models import Min, Max, Sum, Subquery, OuterRef,Avg
from django.db.models.functions import TruncMinute, TruncHour, TruncDay, TruncWeek, TruncMonth
from django.http import JsonResponse
from .models import CoinHistory
from django.db.models import F, ExpressionWrapper, DateTimeField, Func, IntegerField
import time
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
import pytz


def coin_history(request, coin_id):
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')

    if not start_str or not end_str:
        return JsonResponse({'error': '缺少 start 或 end 參數'}, status=400)

    start = parse_datetime(start_str)
    end = parse_datetime(end_str)

    if not start or not end:
        return JsonResponse({'error': 'start 或 end 參數格式錯誤'}, status=400)

    if start >= end:
        return JsonResponse({'error': 'start 需早於 end'}, status=400)

    # 查詢資料，注意這裡假設 date 存的是 UTC 時間
    qs = CoinHistory.objects.filter(
        coin_id=coin_id,
        date__gte=start,
        date__lte=end
    ).order_by('date')

    data = []
    for item in qs:
        # amCharts 需要 timestamp (毫秒)
        timestamp = int(item.date.timestamp() * 1000)
        data.append({
            "date": timestamp,
            "open": float(item.open_price),
            "high": float(item.high_price),
            "low": float(item.low_price),
            "close": float(item.close_price),
            "volume": float(item.volume)
        })

    return JsonResponse({"data": data})

@login_required
def delete_account(request):
    if request.method == "POST":
        password = request.POST.get("password_confirm")
        user = request.user

        if not user.check_password(password):  # 驗證密碼是否正確
            messages.error(request, "密碼錯誤，請重新輸入！")
            return redirect("user_profile")

        messages.success(request, "您的帳號已成功刪除！")
        logout(request)
        user.delete()
        return redirect("home")

    return redirect("user_profile")
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import json
from .models import UserProfile

@login_required
def membership_plans(request):
    return render(request, 'membership_plans.html')

@login_required
@csrf_exempt
def process_payment(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            plan = data.get('plan')
            card_number = data.get('cardNumber')
            expiration_date = data.get('expirationDate')
            cvv = data.get('cvv')

            if not card_number or not expiration_date or not cvv:
                return JsonResponse({'success': False, 'message': '支付資訊不完整'})

            if plan not in ['monthly', 'yearly']:
                return JsonResponse({'success': False, 'message': '無效的方案'})

            # 假設支付成功（這裡應該整合 Stripe/PayPal 等）
            if card_number.startswith("4242"):  
                user_profile = request.user.profile
                user_profile.membership = 'premium'
                user_profile.save()
                return JsonResponse({'success': True, 'message': '支付成功，已升級為 Premium 會員！'})
            else:
                return JsonResponse({'success': False, 'message': '支付失敗，請檢查信用卡資訊'})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '請求格式錯誤'})

    return JsonResponse({'success': False, 'message': '無效的請求方式'})


@login_required
def upgrade_to_premium(request):
    if request.method == 'POST':
        user = request.user.profile
        print(user)
        user.membership = 'premium'
        user.save()

        return JsonResponse({'success': True})
    return JsonResponse({'success': False})




from django.utils import timezone
from .models import SignIn
@login_required
def sign_in(request):
    user = request.user
    today = timezone.now().date()

    # 确保每个用户在数据库中都有一条签到记录，如果没有则自动创建
    sign_in_record, created = SignIn.objects.get_or_create(user=user)

    # 如果今天已经签到过了
    if sign_in_record.last_sign_in_date == today:
        messages.info(request, "今天已簽到過，請明天再來！")
        return redirect('user_profile')

    # 否则，进行签到
    sign_in_record.update_consecutive_sign_in()  # 更新连续签到次数
    sign_in_record.last_sign_in_date = today
    sign_in_record.sign_in_count += 1
    sign_in_record.save()

    messages.success(request, "簽到成功！")
    referer = request.META.get('HTTP_REFERER', '/')
    return redirect(referer)

@login_required
def user_profile(request):
    today = timezone.now().date()
    return render(request, 'myapp/user_profile.html', {'today': today})

#使用者條款
from django.shortcuts import render

def user_terms(request):
    return render(request, 'user_terms.html')




from django.shortcuts import render

def guanggao_shenfen_queren(request):
    # 預設顯示廣告
    ad_show = True

    # 檢查用戶是否已登入並且是 premium 用戶
    if request.user.is_authenticated:
        # 確保用戶有 Profile
        try:
            user_profile = request.user.profile
            if user_profile.membership == 'premium':
                ad_show = True  # premium 用戶不顯示廣告
        except user_profile.DoesNotExist:
            ad_show = True  # 如果沒有 profile，預設為 free 用戶，顯示廣告
    else:
        ad_show = True  # 未登入用戶視為 free，用戶，顯示廣告

    # 返回渲染頁面並傳遞 ad_show 變數
    return render(request, 'home.html', {'ad_show': ad_show})

from django.shortcuts import render
from django.db.models import OuterRef, Subquery
from .models import Coin, BitcoinPrice

def favorite_coins(request):
    if not request.user.is_authenticated:
        return render(request, 'favorites.html', {'favorite_cryptos': []})

    # 取最新價格資料
    latest_price = BitcoinPrice.objects.filter(
        coin=OuterRef('pk')
    ).order_by('-timestamp')

    # 注入最新價格欄位
    favorite_cryptos = request.user.profile.favorite_coin.annotate(
        usd_display=Subquery(latest_price.values('usd')[:1]),
        market_cap_display=Subquery(latest_price.values('market_cap')[:1]),
        volume_24h_display=Subquery(latest_price.values('volume_24h')[:1]),
        change_24h=Subquery(latest_price.values('change_24h')[:1])
    )

    return render(request, 'favorite_coins.html', {
        'favorite_cryptos': favorite_cryptos
    })

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from main.models import UserProfile, BitcoinPrice, Coin

@login_required
def favorite_coins(request):
    # 取得使用者收藏的幣種
    profile = request.user.profile
    favorite_coins = profile.favorite_coin.all()

    favorite_cryptos = []
    for coin in favorite_coins:
        # 取得最新價格資料
        latest_price = BitcoinPrice.objects.filter(coin=coin).order_by('-timestamp').first()
        if latest_price:
            favorite_cryptos.append({
                'id': coin.id,
                'coinname': coin.coinname,
                'logo_url': coin.logo_url,
                'usd_display': "{:,.2f}".format(latest_price.usd),
                'market_cap_display': "{:,.2f}".format(latest_price.market_cap or 0),
                'volume_24h_display': "{:,.2f}".format(latest_price.volume_24h or 0),
                'change_24h': latest_price.change_24h or 0,
            })
        else:
            # 沒有價格資料時填 0
            favorite_cryptos.append({
                'id': coin.id,
                'coinname': coin.coinname,
                'logo_url': coin.logo_url,
                'usd_display': "0.00",
                'market_cap_display': "0.00",
                'volume_24h_display': "0.00",
                'change_24h': 0,
            })

    context = {
        'favorite_cryptos': favorite_cryptos,
    }
    return render(request, 'favorite_coins.html', context)



@login_required
def submit_questionnaire(request):
    print("收到 POST：", request.POST)
    if request.method == "POST":
        user = request.user

        for key in request.POST:
            if key.startswith("question_"):
                question_id = key.split("_")[1]
                try:
                    question = FeedbackQuestion.objects.get(pk=question_id)
                except FeedbackQuestion.DoesNotExist:
                    continue

                if question.question_type == "checkbox":
                    # 多選題：取得所有選項值
                    answers = request.POST.getlist(key)
                    for ans in answers:
                        FeedbackAnswer.objects.create(
                            user=user,
                            question=question,
                            answer_text=ans,
                            submitted_at=now()
                        )
                else:
                    # 單選 / 滿意度 / 下拉選單 / 開放填答
                    answer = request.POST.get(key)
                    print(f"儲存：user={user}, question={question.id}, answer={answer}")
                    if answer:
                        FeedbackAnswer.objects.create(
                            user=user,
                            question=question,
                            answer_text=answer,
                            submitted_at=now()
                        )

        return redirect('/')

@csrf_exempt
def track_impression(request):
    data = json.loads(request.body)
    page = data.get("page", "/")
    tracker, _ = PageTracker.objects.get_or_create(page_name=page)
    tracker.impressions += 1
    tracker.save()
    return JsonResponse({'status': 'ok'})

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def coin_history_api(request):
    coin_id = request.GET.get('coin_id')
    if not coin_id:
        return JsonResponse({'error': '缺少 coin_id 參數'}, status=400)

    try:
        selected_coin = Coin.objects.get(id=coin_id)
    except Coin.DoesNotExist:
        return JsonResponse({'error': '查無此幣種'}, status=404)

    thirty_days_ago = timezone.now().date() - timedelta(days=60)

    queryset = (
        CoinHistory.objects
        .filter(coin_id=coin_id, date__gte=thirty_days_ago)
        .select_related('coin')
        .order_by('date')
    )

    fields = ['date', 'close_price', 'high_price', 'low_price', 'volume']
    print(fields)  # 確認沒有空字串

    # 1️⃣ 先把 queryset 讀成 DataFrame
    df = pd.DataFrame.from_records(queryset.values(*fields))

    # 2️⃣ 再把數值欄位轉成 float，避免 Decimal 與 float 運算錯誤
    for col in ['close_price', 'high_price', 'low_price', 'volume']:
        if col in df.columns:
            df[col] = df[col].astype(float)

    if df.empty:
        return JsonResponse({'error': '此時間區間無資料'}, status=204)

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')

    df['ema20'] = ta.trend.EMAIndicator(close=df['close_price'], window=20).ema_indicator()
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close_price'], window=14).rsi()
    df = df.dropna(subset=['ema20', 'rsi'])

    bb = ta.volatility.BollingerBands(close=df['close_price'], window=20, window_dev=2)
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()

    stoch = ta.momentum.StochasticOscillator(
        high=df['high_price'], low=df['low_price'], close=df['close_price'], window=14
    )
    df['stoch'] = stoch.stoch()

    df['cci'] = ta.trend.CCIIndicator(
        high=df['high_price'], low=df['low_price'], close=df['close_price'], window=20
    ).cci()

    df['williams_r'] = ta.momentum.WilliamsRIndicator(
        high=df['high_price'], low=df['low_price'], close=df['close_price'], lbp=14
    ).williams_r()

    df['obv'] = ta.volume.OnBalanceVolumeIndicator(close=df['close_price'], volume=df['volume']).on_balance_volume()
    df['mfi'] = ta.volume.MFIIndicator(
        high=df['high_price'], low=df['low_price'], close=df['close_price'], volume=df['volume'], window=14
    ).money_flow_index()

    df['atr'] = ta.volatility.AverageTrueRange(
        high=df['high_price'], low=df['low_price'], close=df['close_price'], window=14
    ).average_true_range()

    import math

    def safe_list(values):
        """把 NaN 或 None 轉成 None，方便 JSON 回傳"""
        return [v if v is not None and not (isinstance(v, float) and math.isnan(v)) else None for v in values]


    chart_data = {
        'coin_id': int(coin_id),
        'selected_coin_name': selected_coin.coinname,
        'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),

        # 價格相關
        'close': safe_list(df['close_price'].tolist()),
        'ema20': safe_list(df['ema20'].round(2).tolist()),
        'bb_high': safe_list(df['bb_high'].round(2).tolist()),
        'bb_low': safe_list(df['bb_low'].round(2).tolist()),

        # 動能指標
        'rsi': safe_list(df['rsi'].round(2).tolist()),
        'stoch': safe_list(df['stoch'].round(2).tolist()),
        'cci': safe_list(df['cci'].round(2).tolist()),
        'williams_r': safe_list(df['williams_r'].round(2).tolist()),

        # 成交量
        'obv': safe_list(df['obv'].round(2).tolist()),
        'mfi': safe_list(df['mfi'].round(2).tolist()),

        # 波動率
        'atr': safe_list(df['atr'].round(2).tolist())
    }

    return JsonResponse(chart_data, encoder=DecimalEncoder, safe=False)


import os
import pandas as pd
import numpy as np
import traceback
import joblib
from django.http import JsonResponse
from sklearn.ensemble import RandomForestClassifier

# ----------- 特徵工程 -----------
def add_features(df):
    df = df.copy()
    df["return"] = df["close_price"].pct_change()
    df["ma5"] = df["close_price"].rolling(5).mean()
    df["ma20"] = df["close_price"].rolling(20).mean()
    # 標籤：明天漲跌（回測用，不影響已訓練模型）
    df["label"] = (df["close_price"].shift(-1) > df["close_price"]).astype(int)
    df["vol_ma5"] = df["volume"].rolling(5).mean()
    df["vol_ratio"] = df["volume"] / (df["vol_ma5"] + 1e-6)
    df = df.dropna().reset_index(drop=True)
    return df

# ----------- 使用已訓練模型回測 -----------
def backtest_with_model(df, model):
    df = add_features(df)

    # 與模型訓練一致的特徵
    features = ["ma5", "ma20", "return", "vol_ratio"]
    df = df.dropna(subset=features).reset_index(drop=True)

    # 模型預測
    df["pred"] = model.predict(df[features])

    # 策略報酬
    df["strategy"] = df["pred"].shift(1) * df["return"]
    df["strategy"].fillna(0, inplace=True)
    df["cum_strategy"] = (1 + df["strategy"]).cumprod()
    df["cum_buy_hold"] = (1 + df["return"]).cumprod()

    return df

def backtest_view(request):
    try:
        current_dir = os.path.dirname(__file__)

        # 取得 coin_id
        coin_param = request.GET.get('coin_id')
        if not coin_param:
            return JsonResponse({'error': '缺少 coin_id 參數'}, status=400)

        try:
            coin_list = [int(c.strip()) for c in coin_param.split(',')]
        except ValueError:
            return JsonResponse({'error': 'coin_id 格式錯誤'}, status=400)

        # 模型路徑
        model_path = os.path.abspath(os.path.join(current_dir, "../data_analysis/backtest/BackTest0925-2.pkl"))

        # 載入已訓練模型
        if os.path.exists(model_path):
            model = joblib.load(model_path)
            print("已載入訓練好的模型")
        else:
            return JsonResponse({'error': '模型不存在'}, status=500)

        result_data = {}

        for coin_id in coin_list:
            try:
                selected_coin = Coin.objects.get(id=coin_id)
            except Coin.DoesNotExist:
                continue  # 找不到就跳過

            # 從資料庫取出 CoinHistory
            queryset = (
                CoinHistory.objects
                .filter(coin_id=coin_id)
                .select_related('coin')
                .order_by('date')
            )

            fields = ['date', 'close_price', 'high_price', 'low_price', 'volume']
            df = pd.DataFrame.from_records(queryset.values(*fields))

            if df.empty:
                continue  # 沒有資料就跳過

            # 將 Decimal 欄位轉 float
            for col in ['close_price', 'high_price', 'low_price', 'volume']:
                df[col] = df[col].astype(float)

            # 技術指標計算
            df["ema20"] = df["close_price"].ewm(span=20, adjust=False).mean()

            delta = df["close_price"].diff()
            gain = np.where(delta > 0, delta, 0)
            loss = np.where(delta < 0, -delta, 0)
            avg_gain = pd.Series(gain).rolling(window=14).mean()
            avg_loss = pd.Series(loss).rolling(window=14).mean()
            df["rsi"] = 100 - (100 / (1 + avg_gain / (avg_loss + 1e-10)))

            # 使用已訓練模型回測
            g = backtest_with_model(df, model)
            print(g)
            print(g["pred"].value_counts())
            print(g[["ma5","ma20","return","pred"]])

            # 計算策略績效（最後一天累積報酬）
            strategy_final = g["cum_strategy"].iloc[-1]
            buy_hold_final = g["cum_buy_hold"].iloc[-1]

            # 可以選擇用百分比表示
            strategy_pct = (strategy_final - 1) * 100
            buy_hold_pct = (buy_hold_final - 1) * 100

            result_data[coin_id] = {
                "coin_name": selected_coin.coinname,
                "dates": g["date"].dt.strftime("%Y-%m-%d").tolist(),
                "strategy": g["cum_strategy"].astype(float).tolist(),
                "buy_hold": g["cum_buy_hold"].astype(float).tolist(),
                "close": g["close_price"].astype(float).tolist(),
                "ema20": g["ema20"].astype(float).fillna(0).tolist(),
                "rsi": g["rsi"].astype(float).fillna(0).tolist(),
                "strategy_final": strategy_final,          # ✅ 累積報酬數值
                "buy_hold_final": buy_hold_final,          # ✅ 累積報酬數值
                "strategy_pct": round(strategy_pct, 2),    # ✅ 百分比
                "buy_hold_pct": round(buy_hold_pct, 2),    # ✅ 百分比
            }

    # ============ 🔽 這裡加 GPT 分析 🔽 ============
        analysis_prompt = f"""
        以下是加密貨幣回測的數據：
        {json.dumps(result_data, ensure_ascii=False)}

        請幫我做以下事情：
        1. 比較每個幣種策略 vs Buy&Hold 的最終報酬率。
        2. 評估策略表現是否優於 Buy&Hold。
        3. 指出哪個幣種的策略表現最佳，以及哪個最差。
        4. 提供投資上的建議（例如：是否適合長期持有、需注意的風險）。
        請用中文回答，並條列重點。
        """

        url = "https://free.v36.cm/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api}",  # 你的 API KEY
            "Content-Type": "application/json",
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "你是一位專業的加密貨幣投資顧問。"},
                {"role": "user", "content": analysis_prompt}
            ]
        }

        gpt_response = requests.post(url, headers=headers, json=data)
        gpt_response.raise_for_status()
        gpt_result = gpt_response.json()
        gpt_reply = gpt_result["choices"][0]["message"]["content"]

        # ✅ 把 GPT 分析加進回傳
        return JsonResponse({
            "result_data": result_data,
            "gpt_analysis": gpt_reply
        })

    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)