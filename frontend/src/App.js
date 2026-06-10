import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { TrendingUp, TrendingDown, Leaf, Bell, Upload, RefreshCw, Cloud, Download, MapPin } from 'lucide-react';
import './App.css';

const API = 'https://elananu-agriprice-forecasting.hf.space';
const COLORS = {
  coconut:'#f59e0b', onion:'#ef4444', tomato:'#f97316',
  rice:'#10b981', banana:'#eab308', wheat:'#a78bfa',
  potato:'#60a5fa', garlic:'#f472b6', chilli:'#ff6b6b',
  turmeric:'#fbbf24', sugarcane:'#34d399'
};
const CITIES = ['Chennai','Mumbai','Delhi','Bangalore','Kolkata'];

function App() {
  const [summary, setSummary]           = useState([]);
  const [selected, setSelected]         = useState('coconut');
  const [prediction, setPrediction]     = useState(null);
  const [history, setHistory]           = useState([]);
  const [weather, setWeather]           = useState(null);
  const [alerts, setAlerts]             = useState([]);
  const [seasonal, setSeasonal]         = useState(null);
  const [multiCity, setMultiCity]       = useState(null);
  const [livePrice, setLivePrice]       = useState(null);
  const [loading, setLoading]           = useState(true);
  const [uploading, setUploading]       = useState(false);
  const [uploadMsg, setUploadMsg]       = useState('');
  const [showAlerts, setShowAlerts]     = useState(false);
  const [showUpload, setShowUpload]     = useState(false);
  const [userAlerts, setUserAlerts]     = useState([]);
  const [alertForm, setAlertForm]       = useState({commodity:'coconut',type:'above',price:''});
  const [triggered, setTriggered]       = useState([]);
  const [forecastDays, setForecastDays] = useState(7);
  const [selectedCity, setSelectedCity] = useState('Chennai');
  const [activeTab, setActiveTab]       = useState('forecast');
  const [lastRefresh, setLastRefresh]   = useState(new Date());
  const [unit, setUnit]                 = useState('kg');

  const fetchSummary = useCallback(() => {
    axios.get(`${API}/summary?city=${selectedCity}`)
      .then(r => setSummary(r.data.summary)).catch(()=>{});
  }, [selectedCity]);

  useEffect(() => {
    fetchSummary();
    axios.get(`${API}/weather?city=${selectedCity}`).then(r => setWeather(r.data)).catch(()=>{});
    axios.get(`${API}/alerts`).then(r => setAlerts(r.data.alerts)).catch(()=>{});
    const interval = setInterval(() => { fetchSummary(); setLastRefresh(new Date()); }, 30000);
    return () => clearInterval(interval);
  }, [fetchSummary, selectedCity]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      axios.get(`${API}/predict/${selected}?days=${forecastDays}&city=${selectedCity}`),
      axios.get(`${API}/history/${selected}`),
      axios.get(`${API}/seasonal/${selected}`),
      axios.get(`${API}/multicity/${selected}`)
    ]).then(([pred, hist, seas, mc]) => {
      setPrediction(pred.data);
      setHistory(hist.data.history.slice(-30));
      setSeasonal(seas.data);
      setMultiCity(mc.data);
    }).catch(()=>{}).finally(() => setLoading(false));
  }, [selected, forecastDays, selectedCity]);

  useEffect(() => {
    const interval = setInterval(() => {
      axios.get(`${API}/live/${selected}`).then(r => setLivePrice(r.data)).catch(()=>{});
    }, 5000);
    return () => clearInterval(interval);
  }, [selected]);

  useEffect(() => {
    if (summary.length > 0 && userAlerts.length > 0) {
      const fired = [];
      userAlerts.forEach(a => {
        const item = summary.find(s => s.commodity.toLowerCase() === a.commodity);
        if (item) {
          if (a.type === 'above' && item.current_price > a.price)
            fired.push(`🔔 ${a.commodity.toUpperCase()} ₹${item.current_price}/kg — above your alert ₹${a.price}`);
          if (a.type === 'below' && item.current_price < a.price)
            fired.push(`🔔 ${a.commodity.toUpperCase()} ₹${item.current_price}/kg — below your alert ₹${a.price}`);
        }
      });
      setTriggered(fired);
    }
  }, [summary, userAlerts]);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true); setUploadMsg('');
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await axios.post(`${API}/upload`, formData);
      setUploadMsg('✅ ' + res.data.message);
      fetchSummary();
    } catch { setUploadMsg('❌ Upload failed.'); }
    setUploading(false);
  };

  const handleExport = (type) => {
    window.open(`${API}/export/${type}/${selected}?days=${forecastDays}&city=${selectedCity}`, '_blank');
  };

  const getDisplayPrice = (price) => {
    if (!price) return '₹0';
    if (unit === 'ton')     return `₹${(price * 1000).toLocaleString()}`;
    if (unit === 'quintal') return `₹${(price * 100).toLocaleString()}`;
    return `₹${price}`;
  };

  const color       = COLORS[selected] || '#10b981';
  const actionColor = prediction?.action === 'SELL' ? '#ef4444' :
                      prediction?.action === 'BUY'  ? '#10b981' : '#888';

  return (
    <div className="app">

      {/* Header */}
      <header className="header">
        <div className="header-left">
          <Leaf size={26} color="#10b981" />
          <div>
            <h1>AgriPrice Forecasting</h1>
            <span className="subtitle">AI-Powered Agricultural Market Intelligence • v3.0</span>
          </div>
        </div>
        <div className="header-right">
          <span className="refresh-time">🔄 {lastRefresh.toLocaleTimeString()}</span>
          <div className="header-btns">
            <button className="hbtn" onClick={() => {setShowAlerts(!showAlerts); setShowUpload(false);}}>
              <Bell size={14}/> Alerts
              {(alerts.length+userAlerts.length)>0 &&
                <span className="badge">{alerts.length+userAlerts.length}</span>}
            </button>
            <button className="hbtn" onClick={() => {setShowUpload(!showUpload); setShowAlerts(false);}}>
              <Upload size={14}/> Upload CSV
            </button>
            <button className="hbtn export-btn" onClick={() => handleExport('excel')}>
              <Download size={14}/> Excel
            </button>
            <button className="hbtn pdf-btn" onClick={() => handleExport('pdf')}>
              <Download size={14}/> PDF
            </button>
          </div>
        </div>
      </header>

      {/* Triggered Alerts */}
      {triggered.map((t,i) => <div key={i} className="trigger-banner">{t}</div>)}

      {/* Upload Panel */}
      {showUpload && (
        <div className="panel mb16">
          <h3>📂 Upload Dataset</h3>
          <p className="hint">Required columns: <code>date, commodity, market, price, unit, state</code></p>
          <label className="upload-area">
            <Upload size={28} color="#10b981"/>
            <span>{uploading ? '⏳ Processing...' : 'Click to select CSV file'}</span>
            <input type="file" accept=".csv" onChange={handleUpload} style={{display:'none'}}/>
          </label>
          {uploadMsg && <p className={uploadMsg.startsWith('✅') ? 'success-msg':'error-msg'}>{uploadMsg}</p>}
        </div>
      )}

      {/* Alerts Panel */}
      {showAlerts && (
        <div className="panel mb16">
          <h3>🔔 Price Alerts</h3>
          {alerts.length > 0 && (
            <div className="mb12">
              <h4>📊 AI Market Alerts</h4>
              {alerts.map((a,i) => (
                <div key={i} className={`alert-item ${a.type} sev-${a.severity}`}>
                  <span>{a.type==='rise'?'📈':'📉'} {a.message}</span>
                  <span className={`pct ${a.type}`}>{a.type==='rise'?'+':''}{a.change_pct}%</span>
                </div>
              ))}
            </div>
          )}
          <div>
            <h4>⚙️ My Custom Alerts</h4>
            <div className="alert-form">
              <select value={alertForm.commodity}
                onChange={e=>setAlertForm({...alertForm,commodity:e.target.value})}>
                {Object.keys(COLORS).map(c =>
                  <option key={c} value={c}>{c.charAt(0).toUpperCase()+c.slice(1)}</option>)}
              </select>
              <select value={alertForm.type}
                onChange={e=>setAlertForm({...alertForm,type:e.target.value})}>
                <option value="above">Price goes above</option>
                <option value="below">Price goes below</option>
              </select>
              <input type="number" placeholder="₹ price" value={alertForm.price}
                onChange={e=>setAlertForm({...alertForm,price:e.target.value})}/>
              <button onClick={()=>{
                if(!alertForm.price) return;
                setUserAlerts(p=>[...p,{...alertForm,price:parseFloat(alertForm.price)}]);
                setAlertForm(p=>({...p,price:''}));
              }}>+ Add</button>
            </div>
            {userAlerts.length===0
              ? <p className="no-alert">No custom alerts set.</p>
              : userAlerts.map((a,i)=>(
                <div key={i} className="alert-item user-alert">
                  <span>🔔 {a.commodity} {a.type} ₹{a.price}/kg</span>
                  <button onClick={()=>setUserAlerts(p=>p.filter((_,idx)=>idx!==i))}>✕</button>
                </div>
              ))
            }
          </div>
        </div>
      )}

      {/* Weather Bar */}
      {weather && (
        <div className="weather-bar">
          <div className="weather-left">
            <Cloud size={18} color="#60a5fa"/>
            <span className="weather-city">{weather.city}</span>
            <span className="weather-temp">{weather.temperature}°C</span>
            <span className="weather-desc">{weather.description}</span>
            <span className="weather-stat">💧 {weather.humidity}%</span>
            <span className="weather-stat">🌬️ {weather.wind_speed} m/s</span>
          </div>
          <div className="weather-impact">{weather.impact}</div>
        </div>
      )}

      {/* Controls Bar */}
      <div className="controls-bar">
        <div className="control-group">
          <MapPin size={14} color="#888"/>
          <label>City:</label>
          <select value={selectedCity} onChange={e=>setSelectedCity(e.target.value)}
            className="ctrl-select">
            {CITIES.map(c=><option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="control-group">
          <label>Forecast:</label>
          {[7,30,90,365].map(d=>(
            <button key={d} className={`day-btn ${forecastDays===d?'active':''}`}
              onClick={()=>setForecastDays(d)}>{d}D</button>
          ))}
        </div>
        <div className="control-group">
          <label>Unit:</label>
          {['kg','quintal','ton'].map(u=>(
            <button key={u} className={`day-btn ${unit===u?'active':''}`}
              onClick={()=>setUnit(u)}>{u}</button>
          ))}
        </div>
      </div>

      {/* Commodity Cards */}
      <section className="cards">
        {summary.map(item => {
          const k    = item.commodity.toLowerCase();
          const isUp = item.change >= 0;
          return (
            <div key={k} className={`card ${selected===k?'card-active':''}`}
              onClick={()=>setSelected(k)}
              style={selected===k?{borderColor:COLORS[k]}:{}}>
              <div className="card-name">{item.commodity}</div>
              <div className="card-price" style={{color:COLORS[k]}}>
                {getDisplayPrice(item.current_price)}/{unit}
              </div>
              <div className={`card-change ${isUp?'up':'down'}`}>
                {isUp?'▲':'▼'} {item.change_pct}%
              </div>
              <div className="card-range">
                {getDisplayPrice(item.min_price)}–{getDisplayPrice(item.max_price)}
              </div>
            </div>
          );
        })}
      </section>

      {/* Live Ticker */}
      {livePrice && (
        <div className="live-ticker">
          <span className="live-dot"></span>
          <span className="live-label">LIVE</span>
          <span>{livePrice.commodity}</span>
          <span className="live-price" style={{color}}>
            {getDisplayPrice(livePrice.live_price)}/{unit}
          </span>
          <span className="live-time">{livePrice.timestamp}</span>
          <span className="live-note">auto-refresh 5s</span>
        </div>
      )}

      {loading && (
        <div className="loading">
          <RefreshCw size={18} className="spin"/> Loading...
        </div>
      )}

      {prediction && !loading && (
        <main className="main">

          {/* Action Card */}
          <div className="action-card" style={{borderColor: actionColor}}>
            <div className="action-left">
              <div className="action-signal" style={{background: actionColor}}>
                {prediction.action}
              </div>
              <div>
                <div className="action-commodity">{prediction.commodity} — {prediction.city}</div>
                <div className="action-rec">{prediction.recommendation}</div>
                {prediction.festival_alert &&
                  <div className="festival-alert">{prediction.festival_alert}</div>}
              </div>
            </div>
            <div className="action-prices">
              <div className="price-block">
                <span className="price-label">Per kg</span>
                <span className="price-val" style={{color}}>₹{prediction.current_price}</span>
              </div>
              <div className="price-block">
                <span className="price-label">Per Quintal</span>
                <span className="price-val">₹{(prediction.current_per_ton/10).toFixed(2)}</span>
              </div>
              <div className="price-block">
                <span className="price-label">Per Ton</span>
                <span className="price-val">₹{prediction.current_per_ton?.toLocaleString()}</span>
              </div>
              <div className="price-block">
                <span className="price-label">Season</span>
                <span className="price-val">{prediction.season}</span>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="tabs">
            {['forecast','history','seasonal','multicity'].map(t=>(
              <button key={t} className={`tab ${activeTab===t?'tab-active':''}`}
                onClick={()=>setActiveTab(t)}>
                {t==='forecast'  ? '📈 Forecast'  :
                 t==='history'   ? '📉 History'   :
                 t==='seasonal'  ? '🌿 Seasonal'  : '🗺️ Multi-City'}
              </button>
            ))}
          </div>

          {/* Forecast Tab */}
          {activeTab==='forecast' && (
            <section className="panel">
              <div className="panel-header">
                <h2>{forecastDays}-Day Price Forecast — {prediction.commodity}</h2>
                <span className={`trend-badge ${prediction.trend}`}>
                  {prediction.trend==='rising'
                    ? <TrendingUp size={13}/>
                    : <TrendingDown size={13}/>}
                  {prediction.change_pct}%
                </span>
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={prediction.predictions.slice(0, forecastDays)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222"/>
                  <XAxis dataKey="date" tick={{fontSize:10,fill:'#666'}}
                    tickFormatter={d=>d.slice(5)}
                    interval={Math.floor(forecastDays/7)}/>
                  <YAxis tick={{fontSize:10,fill:'#666'}}/>
                  <Tooltip contentStyle={{background:'#1a1a1a',border:'1px solid #333'}}
                    formatter={v=>[`₹${v}/kg`,'Price']}/>
                  <Line type="monotone" dataKey="price" stroke={color}
                    strokeWidth={2} dot={forecastDays<=30}/>
                </LineChart>
              </ResponsiveContainer>
              {forecastDays <= 30 && (
                <div className="pred-grid">
                  {prediction.predictions.slice(0,forecastDays).map(p=>(
                    <div key={p.date} className="pred-item">
                      <div className="pred-date">{p.date.slice(5)}</div>
                      <div className="pred-price" style={{color}}>₹{p.price}</div>
                      <div className="pred-ton">₹{(p.price*100).toFixed(0)}/q</div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* History Tab */}
          {activeTab==='history' && (
            <section className="panel">
              <h2>📉 Price History — Last 30 Days</h2>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222"/>
                  <XAxis dataKey="date" tick={{fontSize:10,fill:'#666'}}/>
                  <YAxis tick={{fontSize:10,fill:'#666'}}/>
                  <Tooltip contentStyle={{background:'#1a1a1a',border:'1px solid #333'}}
                    formatter={v=>[`₹${v}/kg`,'Price']}/>
                  <Line type="monotone" dataKey="price" stroke={color}
                    strokeWidth={2} dot={false}/>
                </LineChart>
              </ResponsiveContainer>
            </section>
          )}

          {/* Seasonal Tab */}
          {activeTab==='seasonal' && seasonal && (
            <section className="panel">
              <h2>🌿 Seasonal Analysis — {seasonal.commodity}</h2>
              <div className="seasonal-info">
                <div className="seasonal-badge green">🛒 Best Buy: {seasonal.best_buy_season}</div>
                <div className="seasonal-badge red">💰 Best Sell: {seasonal.best_sell_season}</div>
                <div className="seasonal-badge blue">📅 Current: {seasonal.current_season}</div>
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={seasonal.seasonal}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222"/>
                  <XAxis dataKey="season" tick={{fontSize:11,fill:'#888'}}/>
                  <YAxis tick={{fontSize:11,fill:'#888'}}/>
                  <Tooltip contentStyle={{background:'#1a1a1a',border:'1px solid #333'}}
                    formatter={v=>[`₹${v}/kg`]}/>
                  <Bar dataKey="avg_price" fill={color} radius={[4,4,0,0]}/>
                </BarChart>
              </ResponsiveContainer>
            </section>
          )}

          {/* Multi-City Tab */}
          {activeTab==='multicity' && multiCity && (
            <section className="panel">
              <h2>🗺️ Multi-City Prices — {multiCity.commodity}</h2>
              <table className="summary-table">
                <thead>
                  <tr>
                    <th>City</th><th>Per kg</th>
                    <th>Per Quintal</th><th>Per Ton</th><th>Recommendation</th>
                  </tr>
                </thead>
                <tbody>
                  {multiCity.cities.map(c=>(
                    <tr key={c.city} className={c.city===selectedCity?'row-active':''}>
                      <td style={{fontWeight:600}}>{c.city}</td>
                      <td style={{color}}>₹{c.price_per_kg}</td>
                      <td>₹{c.price_quintal}</td>
                      <td>₹{c.price_per_ton.toLocaleString()}</td>
                      <td>
                        <span className={`rec-badge ${
                          c.recommendation.includes('Buy')  ? 'green' :
                          c.recommendation.includes('Sell') ? 'red'   : 'gray'}`}>
                          {c.recommendation}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {/* Market Overview Table */}
          <section className="panel">
            <h2>📊 Market Overview — {selectedCity}</h2>
            <table className="summary-table">
              <thead>
                <tr>
                  <th>Commodity</th><th>Price/kg</th><th>Price/Ton</th>
                  <th>Change</th><th>Avg</th><th>Min</th><th>Max</th>
                </tr>
              </thead>
              <tbody>
                {summary.map(item=>{
                  const k    = item.commodity.toLowerCase();
                  const isUp = item.change >= 0;
                  return (
                    <tr key={k} onClick={()=>setSelected(k)}
                      className={selected===k?'row-active':''}>
                      <td style={{color:COLORS[k],fontWeight:600}}>{item.commodity}</td>
                      <td>₹{item.current_price}</td>
                      <td>₹{item.current_per_ton?.toLocaleString()}</td>
                      <td className={isUp?'up':'down'}>
                        {isUp?'▲':'▼'} ₹{Math.abs(item.change)} ({item.change_pct}%)
                      </td>
                      <td>₹{item.avg_price}</td>
                      <td>₹{item.min_price}</td>
                      <td>₹{item.max_price}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>

        </main>
      )}
    </div>
  );
}

export default App;