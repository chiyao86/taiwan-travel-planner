"""股票預測模型 — XGBoost + PostgreSQL + 特徵工程"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_error
import warnings
warnings.filterwarnings('ignore')

from config import DB_CONFIG, DB_MODE
from services.crawler import get_conn
from services.indicators import calculate_rsi, calculate_macd


def load_stock_data(symbol: str, years: int = 2) -> pd.DataFrame:
    """
    從資料庫讀取指定股票的歷史數據
    
    Args:
        symbol: 股票代號 (如 '2330.TW', 'AAPL')
        years: 讀取過去幾年的數據 (預設 2 年)
    
    Returns:
        DataFrame with columns: trade_date, open, high, low, close, volume
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    
    if DB_MODE == "sqlite":
        query = """
            SELECT trade_date, open_price as open, high_price as high,
                   low_price as low, close_price as close, volume
            FROM stock_prices
            WHERE symbol = ? AND trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date ASC
        """
        conn = get_conn()
        try:
            df = pd.read_sql_query(query, conn, params=(
                symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
        finally:
            conn.close()
    else:
        query = """
            SELECT trade_date, open_price as open, high_price as high,
                   low_price as low, close_price as close, volume
            FROM stock_prices
            WHERE symbol = %s AND trade_date >= %s AND trade_date <= %s
            ORDER BY trade_date ASC
        """
        conn = get_conn()
        try:
            df = pd.read_sql_query(query, conn, params=(symbol, start_date, end_date))
        finally:
            conn.close()
    
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.set_index('trade_date')
    
    print(f"✅ 載入 {symbol} 的 {len(df)} 筆歷史數據 ({start_date.date()} ~ {end_date.date()})")
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    特徵工程：計算技術指標與衍生特徵
    
    特徵包含：
    - MA5, MA20: 移動平均線
    - RSI: 相對強弱指標
    - MACD, MACD_Signal, MACD_Hist: MACD 指標
    - Daily_Return: 每日報酬率
    - Target: 明天的收盤價變動百分比 (預測目標)
    
    Args:
        df: 原始股價 DataFrame (需包含 open, high, low, close, volume)
    
    Returns:
        加入技術指標的 DataFrame
    """
    df = df.copy()
    
    # 移動平均線
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()
    
    # RSI 相對強弱指標
    df['RSI'] = calculate_rsi(df['close'], period=14)
    
    # MACD 指標
    macd, signal, hist = calculate_macd(df['close'])
    df['MACD'] = macd
    df['MACD_Signal'] = signal
    df['MACD_Hist'] = hist
    
    # 每日報酬率
    df['Daily_Return'] = df['close'].pct_change()
    
    # 價格變動幅度
    df['High_Low_Pct'] = (df['high'] - df['low']) / df['low']
    
    # 成交量變動率
    df['Volume_Change'] = df['volume'].pct_change()
    
    # ─── 預測目標：明天的收盤價變動百分比 ───
    df['Target'] = df['close'].pct_change().shift(-1)
    
    # 移除 NaN 值
    df = df.dropna()
    
    print(f"✅ 特徵工程完成，保留 {len(df)} 筆有效數據")
    return df


def train_xgboost_model(df: pd.DataFrame, test_size: float = 0.15, val_size: float = 0.15, early_stopping_rounds: int = 20):
    """
    使用 XGBoost 訓練預測模型（標準三分割：Train/Validation/Test）
    
    Args:
        df: 包含特徵與目標的 DataFrame
        test_size: 測試集比例 (預設 0.15 = 15%)
        val_size: 驗證集比例 (預設 0.15 = 15%)
        early_stopping_rounds: (已棄用，保留參數以維持兼容性)
    
    Returns:
        (trained_model, feature_columns, evaluation_metrics)
    """
    # 定義特徵欄位
    feature_cols = ['open', 'high', 'low', 'close', 'volume',
                    'MA5', 'MA20', 'RSI', 'MACD', 'MACD_Signal', 'MACD_Hist',
                    'Daily_Return', 'High_Low_Pct', 'Volume_Change']
    
    X = df[feature_cols]
    y = df['Target']
    
    # 檢查數據量充足性
    if len(df) < 100:
        print(f"⚠️  警告: 數據量較少 ({len(df)} 筆)，模型預測可能不穩定")
        print(f"   建議: 至少 150 筆，推薦 250+ 筆")
    
    # 時間序列三分割（不打亂順序）：Train / Validation / Test
    train_end = int(len(df) * (1 - test_size - val_size))
    val_end = int(len(df) * (1 - test_size))
    
    X_train = X.iloc[:train_end]
    X_val = X.iloc[train_end:val_end]
    X_test = X.iloc[val_end:]
    
    y_train = y.iloc[:train_end]
    y_val = y.iloc[train_end:val_end]
    y_test = y.iloc[val_end:]
    
    print(f"📊 訓練集: {len(X_train)} 筆 ({len(X_train)/len(df)*100:.1f}%)")
    print(f"   驗證集: {len(X_val)} 筆 ({len(X_val)/len(df)*100:.1f}%)")
    print(f"   測試集: {len(X_test)} 筆 ({len(X_test)/len(df)*100:.1f}%)")
    
    # 數據充足性評估
    data_quality = "優秀 ✅" if len(X_train) >= 350 else "良好 ✅" if len(X_train) >= 180 else "尚可 ⚠️" if len(X_train) >= 100 else "不足 ❌"
    print(f"   數據充足性: {data_quality} (訓練集 {len(X_train)} 筆)")
    
    # XGBoost 參數設定（針對 2 年數據優化）
    params = {
        'objective': 'reg:squarederror',
        'learning_rate': 0.05,          # 降低學習率（數據更多，可以慢慢學）
        'max_depth': 5,                 # 適中的樹深度
        'min_child_weight': 1,          
        'subsample': 0.8,               # 每棵樹使用 80% 樣本
        'colsample_bytree': 0.8,        # 每棵樹使用 80% 特徵
        'gamma': 0,                     
        'reg_alpha': 0.01,              # 輕微 L1 正則化
        'reg_lambda': 0.5,              # 適度 L2 正則化
        'random_state': 42,
        'n_jobs': -1,
        'n_estimators': 300             # 增加迭代次數（數據更多）
    }
    
    # 訓練模型
    model = xgb.XGBRegressor(**params)
    
    print(f"🔧 開始訓練 XGBoost 模型...")
    print(f"   特徵數量: {X_train.shape[1]}")
    print(f"   目標值範圍: [{y_train.min():.6f}, {y_train.max():.6f}]")
    print(f"   目標值標準差: {y_train.std():.6f}")
    
    # 使用驗證集進行模型評估（eval_set）
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val), (X_test, y_test)],
        verbose=True
    )
    
    # 獲取最佳迭代次數（如果有的話）
    best_iteration = getattr(model, 'best_iteration', params['n_estimators'])
    
    print(f"\n✅ 模型訓練完成！")
    print(f"   實際訓練輪數: {best_iteration}")
    print(f"   樹的數量: {len(model.get_booster().get_dump())}")
    
    # 預測與評估（三個數據集）
    y_pred_train = model.predict(X_train)
    y_pred_val = model.predict(X_val)
    y_pred_test = model.predict(X_test)
    
    train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
    val_rmse = np.sqrt(mean_squared_error(y_val, y_pred_val))
    test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
    
    train_mae = mean_absolute_error(y_train, y_pred_train)
    val_mae = mean_absolute_error(y_val, y_pred_val)
    test_mae = mean_absolute_error(y_test, y_pred_test)
    
    print(f"\n📈 模型評估結果（Train / Validation / Test）：")
    print(f"   迭代次數: {best_iteration}")
    print(f"   訓練集   RMSE: {train_rmse:.6f} | MAE: {train_mae:.6f}")
    print(f"   驗證集   RMSE: {val_rmse:.6f} | MAE: {val_mae:.6f}")
    print(f"   測試集   RMSE: {test_rmse:.6f} | MAE: {test_mae:.6f}")
    
    # 診斷特徵重要性
    print(f"\n🔍 特徵重要性診斷：")
    print(f"   feature_importances_ 總和: {model.feature_importances_.sum():.6f}")
    print(f"   非零重要性數量: {np.count_nonzero(model.feature_importances_)}/{len(model.feature_importances_)}")
    
    metrics = {
        'best_iteration': best_iteration,
        'train_rmse': train_rmse,
        'val_rmse': val_rmse,
        'test_rmse': test_rmse,
        'train_mae': train_mae,
        'val_mae': val_mae,
        'test_mae': test_mae
    }
    
    return model, feature_cols, metrics


def generate_signal(symbol: str, model=None, feature_cols=None, threshold: float = 0.005) -> tuple:
    """
    生成交易訊號
    
    Args:
        symbol: 股票代號
        model: 訓練好的 XGBoost 模型 (若為 None 則自動訓練)
        feature_cols: 特徵欄位列表
        threshold: 買入訊號門檻 (預設 0.5% = 0.005)
    
    Returns:
        (signal, predicted_change_pct, latest_close)
        signal: 1 = 買入, 0 = 觀望
        predicted_change_pct: 預測的明日漲跌幅 (%)
        latest_close: 最新收盤價
    """
    # 如果沒有提供模型，則自動訓練
    if model is None or feature_cols is None:
        print(f"\n🤖 開始訓練 {symbol} 的預測模型...")
        df = load_stock_data(symbol, years=2)
        df = engineer_features(df)
        model, feature_cols, _ = train_xgboost_model(df, test_size=0.15, val_size=0.15)
    
    # 載入最新數據
    df = load_stock_data(symbol, years=2)
    df = engineer_features(df)
    
    # 取得最新一筆數據進行預測
    latest_data = df[feature_cols].iloc[-1:].copy()
    latest_close = df['close'].iloc[-1]
    
    # 預測明天的變動百分比
    prediction = model.predict(latest_data)[0]
    predicted_change_pct = prediction * 100  # 轉換為百分比
    
    # 生成訊號
    signal = 1 if prediction > threshold else 0
    
    signal_text = "🟢 買入" if signal == 1 else "⚪ 觀望"
    print(f"\n{'='*60}")
    print(f"📊 {symbol} 交易訊號生成")
    print(f"{'='*60}")
    print(f"最新收盤價: ${latest_close:.2f}")
    print(f"預測明日漲跌: {predicted_change_pct:+.2f}%")
    print(f"訊號門檻: {threshold*100:.2f}%")
    print(f"交易訊號: {signal_text} (signal={signal})")
    print(f"{'='*60}\n")
    
    return signal, predicted_change_pct, latest_close


class StockPredictor:
    """
    股票預測器類別 (可重複使用的模型)
    
    用法:
        predictor = StockPredictor('2330.TW')
        predictor.train()
        signal, change, price = predictor.predict()
    """
    
    def __init__(self, symbol: str, years: int = 2):
        self.symbol = symbol
        self.years = years
        self.model = None
        self.feature_cols = None
        self.metrics = None
        self.df = None
    
    def train(self, test_size: float = 0.15, val_size: float = 0.15, early_stopping_rounds: int = 20):
        """訓練模型"""
        print(f"\n{'='*60}")
        print(f"🚀 開始訓練 {self.symbol} 的預測模型")
        print(f"{'='*60}\n")
        
        self.df = load_stock_data(self.symbol, self.years)
        
        # 檢查數據量（特徵工程會消耗 ~26 筆，需要足夠的訓練/測試集）
        if len(self.df) < 150:
            raise ValueError(
                f"❌ 數據量不足 ({len(self.df)} 筆)\n"
                f"   最少需要: 150 筆原始數據\n"
                f"   推薦使用: 250+ 筆 (約 1 年交易日)\n"
                f"   理想數量: 500+ 筆 (約 2 年以上)"
            )
        
        self.df = engineer_features(self.df)
        self.model, self.feature_cols, self.metrics = train_xgboost_model(
            self.df, test_size=test_size, val_size=val_size, early_stopping_rounds=early_stopping_rounds
        )
        
        print(f"\n✅ {self.symbol} 模型訓練完成！")
        return self
    
    def predict(self, threshold: float = 0.005) -> tuple:
        """生成交易訊號"""
        if self.model is None:
            raise ValueError("❌ 模型尚未訓練，請先執行 train() 方法")
        
        return generate_signal(
            self.symbol,
            model=self.model,
            feature_cols=self.feature_cols,
            threshold=threshold
        )
    
    def get_feature_importance(self) -> pd.DataFrame:
        """取得特徵重要性"""
        if self.model is None:
            raise ValueError("❌ 模型尚未訓練")
        
        importance = pd.DataFrame({
            'feature': self.feature_cols,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        return importance


# ─── 快速測試範例 ───
if __name__ == "__main__":
    # 方法 1: 快速生成訊號 (自動訓練)
    signal, change, price = generate_signal('AAPL', threshold=0.005)
    
    print("\n" + "="*60)
    
    # 方法 2: 使用 StockPredictor 類別 (可重複使用模型)
    predictor = StockPredictor('2330.TW', years=2)
    predictor.train(early_stopping_rounds=20)
    
    # 查看特徵重要性
    print("\n📊 特徵重要性排名：")
    print(predictor.get_feature_importance().to_string(index=False))
    
    # 生成訊號
    signal, change, price = predictor.predict(threshold=0.005)
