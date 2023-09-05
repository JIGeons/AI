import math
import pyupbit
import datetime
import time

access = "BgywsMVAJyaGdKVXgSUpx56UOA2BXhVUlkjNtWy0"
secret = "eafcO54xNiwAJzKSEEmuekZcvEAP2BOrebuOuk6P"

def get_transaction_amount(date, num):
    tickers = pyupbit.get_tickers("KRW")    # KRW를 통해 거래되는 코인만 불러오기
    dic_ticker = {}

    # 코인 목록의 개수 확인
    num_of_tickers = len(tickers)

    # 개수 출력
    print("코인 목록 개수:", num_of_tickers)    

    for ticker in tickers:
        df = pyupbit.get_ohlcv(ticker, date)    # date 기간의 거래대금을 구해준다
        volume_money = 0.0
        
        try:
            # 순위가 바뀔 수 있으니 당일은 포함 X
            for i in range(2,9):
                time.sleep(0.005)
                volume_money += df['close'].iloc[-i] * df['volume'].iloc[-i]

        except (TypeError, KeyError):
            print(f"코인 {ticker}의 데이터를 처리하는 중에 오류 발생")

        dic_ticker[ticker] = volume_money

    # 거래대금 큰 순으로 ticker를 정렬
    sorted_ticker = sorted(dic_ticker.items(), key=lambda x : x[1], reverse=True)

    coin_list = []
    count = 0

    for coin in sorted_ticker:
        count += 1

        # 거래대금이 높은 num 개의 코인만 구한다
        if count <= num:
            coin_list.append(coin[0])
        else:
            break

    return coin_list

def get_rsi(df, period=14):

    # 전일 대비 변동 평균
    df['change'] = df['close'].diff()

    # 상승한 가격과 하락한 가격
    df['up'] = df['change'].apply(lambda x: x if x>0 else 0)
    df['down'] = df['change'].apply(lambda x: -x if x<0 else 0)

    # 상승 평균과 하락 평균
    df['avg_up'] = df['up'].ewm(alpha = 1 / period).mean()
    df['avg_down'] = df['down'].ewm(alpha=1 / period).mean()

    # 상대강도지수(RSI) 계산
    df['rs'] = df['avg_up'] / df['avg_down']
    df['rsi'] = 100 - (100 / (1 + df['rs']))
    rsi = df['rsi']

    return rsi

# 이미 매수한 코인인지 확인
def has_coin(ticker, balances):
    result = False

    for coin in balances:
        coin_ticker = coin['unit_currency'] + "-" + coin['currency']

        if ticker == coin_ticker:
            result = True

    return result

# 수익률 확인
def get_revenue_rate(balances, ticker):
    revenue_rate = 0.0

    for coin in balances:
        # 티커 형태로 전환
        coin_ticker = coin['unit_currency'] + "-" + coin['currency']

        if ticker == coin_ticker:
            # 현재 시세
            now_price = pyupbit.get_current_price(coin_ticker)

            # 수익률 계산을 위한 형 변환
            revenue_rate = (now_price - float(coin['avg_buy_price'])) / float(coin['avg_buy_price']) * 100.0

    return revenue_rate

upbit = pyupbit.Upbit(access, secret)       # 객체 생성

tickers = get_transaction_amount("day", 10)  # 거래대금 상위 10개 코인 선정
print(tickers)

# 현재 날짜를 저장하는 변수
current_date = datetime.datetime.now().date()
while True:
    # 현재 날짜를 다시 확인
    new_date = datetime.datetime.now().date()

    # "2040-01-01" 이면 무한 루프 종료
    if new_date >= datetime.date(2040, 1, 1):
        break

    # 새로운 날짜가 시작되면 해당 블록  실행
    if new_date != current_date:
        tickers = get_transaction_amount("day", 10)  # 거래대금 상위 10개 코인 선정
        current_date = new_date

    balances = upbit.get_balances()

    my_money = 0.0

    if balances:
        my_money = float(balances[0]['balance'])    # 내 원화

    money_rate = 1.0                            # 투자 비중
    money = my_money * money_rate               # 코인에 할당할 비용
    money = math.floor(money)                   # 소수점 버림

    #   count_coin = len(tickers)       # 목표 코인 개수
    #   money /= count_coin             # 각각의 코인에 공평하게 자본 분배

    target_revenue = 1.0            # 목표 수익률(1.0 %)
    #   division_amount = 0.3           # 분할 매도 비중
    target_loss = 3.0               # 1.5% 손실 날시 매도

    for target_ticker in tickers:
        ticker_rate = get_revenue_rate(balances, target_ticker)
        df_minute = pyupbit.get_ohlcv(target_ticker, interval="1")     # 1분봉 정보
        rsi14 = get_rsi(df_minute, 14).iloc[-1]                        # 당일 RSI14 
        before_rsi14 = get_rsi(df_minute, 14).iloc[-2]                 # 작일 RSI14 

        if has_coin(target_ticker, balances):
            ticker_rate = get_revenue_rate(balances, target_ticker) # 수익률 확인

            # 매도 조건 충족1
            if rsi14 < 70 and before_rsi14 > 70:
                amount = upbit.get_balance(target_ticker)      # 현재 비트코인 보유 수량
                upbit.sell_market_order(target_ticker, amount) # 시장가에 매도
                balances = upbit.get_balances()         # 매도했으니 잔고를 최신화!
                print(f"매도 - {target_ticker}: 가격 {amount * pyupbit.get_current_price(target_ticker)}에 {amount}개 판매, 수익률 : {ticker_rate}%")

            # 매도 조건 충족2 (과매수 구간일 때)
            elif rsi14 > 70:
                # 목표 수익률을 만족한다면
                if ticker_rate >= target_revenue:
                    amount = upbit.get_balance(target_ticker)   # 현재 코인 보유 수량
                    sell_amount = amount                          # 분할 매도 비중
                    upbit.buy_market_order(target_ticker, sell_amount)  # 시장가에 매도
                    balances = upbit.get_balances()             # 매도했으니 잔고를 최신화
                    print(f"매도 - {target_ticker}: 가격 {amount * pyupbit.get_current_price(target_ticker)}에 {amount}개 판매, 수익률 : {ticker_rate}%")
            
            # 매도 조건 충족3 (수익률 달성 했을 시)
            elif ticker_rate >= target_revenue:
                amount = upbit.get_balance(target_ticker)   # 현재 코인 보유 수량
                sell_amount = amount                          # 분할 매도 비중
                upbit.buy_market_order(target_ticker, sell_amount)  # 시장가에 매도
                balances = upbit.get_balances()             # 매도했으니 잔고를 최신화
                print(f"매도 - {target_ticker}: 가격 {amount * pyupbit.get_current_price(target_ticker)}에 {amount}개 판매, 수익률 : {ticker_rate}%")

            # 매도 조건 충족4 (1.5% 이하로 내려갈 시 손절)
            elif ticker_rate <= target_loss:
                amount = upbit.get_balance(target_ticker)   # 현재 코인 보유 수량
                sell_amount = amount                          # 분할 매도 비중
                upbit.buy_market_order(target_ticker, sell_amount)  # 시장가에 매도
                balances = upbit.get_balances()             # 매도했으니 잔고를 최신화
                print(f"매도 - {target_ticker}: 가격 {amount * pyupbit.get_current_price(target_ticker)}에 {amount}개 판매, 수익률 : {ticker_rate}%")

        else:
            # 매수 조건 충족
            if rsi14 > 30 and before_rsi14 < 30:
                upbit.buy_market_order(target_ticker, money)   # 시장가에 비트코인을 매수
                balances = upbit.get_balances()         # 매수했으니 잔고를 최신화
                print(f"매수 - {target_ticker}: 가격 {money}에 {money / pyupbit.get_current_price(target_ticker)}개 구매")
