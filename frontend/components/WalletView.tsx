"use client";

import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { useEffect, useState } from "react";
import { LAMPORTS_PER_SOL } from "@solana/web3.js";
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend } from "chart.js";
import { Line, Bar } from "react-chartjs-2";
import "@solana/wallet-adapter-react-ui/styles.css";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend);

interface ForecastData {
  stocks: { labels: string[]; actual: number[]; predicted: number[] };
  crypto: { labels: string[]; actual: number[]; predicted: number[] };
  sentiment: { labels: string[]; values: number[] };
  cloud: { labels: string[]; values: number[] };
}

export const WalletView = () => {
  const { connection } = useConnection();
  const { publicKey } = useWallet();
  const [balance, setBalance] = useState<number | null>(null);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!connection || !publicKey) {
      setBalance(null);
      return;
    }

    const updateBalance = async () => {
      try {
        const bal = await connection.getBalance(publicKey);
        setBalance(bal / LAMPORTS_PER_SOL);
      } catch (e) {
        console.error("Failed to fetch balance", e);
      }
    };

    updateBalance();
    const id = connection.onAccountChange(publicKey, () => updateBalance());
    return () => {
      connection.removeAccountChangeListener(id);
    };
  }, [connection, publicKey]);

  // Fetch forecast data
  useEffect(() => {
    const fetchForecast = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch("/api/dashboard/forecast");
        if (!response.ok) throw new Error("Failed to fetch forecast data");
        const data = await response.json();
        setForecast(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
        console.error("Forecast fetch error:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchForecast();
    const interval = setInterval(fetchForecast, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  const stockChartData = forecast
    ? {
        labels: forecast.stocks.labels,
        datasets: [
          {
            label: "Stock (Actual)",
            data: forecast.stocks.actual,
            borderColor: "rgb(59, 130, 246)",
            backgroundColor: "rgba(59, 130, 246, 0.1)",
            tension: 0.4,
            fill: true,
          },
          {
            label: "Stock (Predicted)",
            data: forecast.stocks.predicted,
            borderColor: "rgb(239, 68, 68)",
            borderDash: [5, 5],
            backgroundColor: "rgba(239, 68, 68, 0.1)",
            tension: 0.4,
            fill: false,
          },
        ],
      }
    : null;

  const cryptoChartData = forecast
    ? {
        labels: forecast.crypto.labels,
        datasets: [
          {
            label: "Crypto (Actual)",
            data: forecast.crypto.actual,
            borderColor: "rgb(34, 197, 94)",
            backgroundColor: "rgba(34, 197, 94, 0.1)",
            tension: 0.4,
            fill: true,
          },
          {
            label: "Crypto (Predicted)",
            data: forecast.crypto.predicted,
            borderColor: "rgb(251, 146, 60)",
            borderDash: [5, 5],
            backgroundColor: "rgba(251, 146, 60, 0.1)",
            tension: 0.4,
            fill: false,
          },
        ],
      }
    : null;

  const sentimentChartData = forecast
    ? {
        labels: forecast.sentiment.labels,
        datasets: [
          {
            label: "Sentiment Score",
            data: forecast.sentiment.values,
            backgroundColor: ["rgb(168, 85, 247)"],
          },
        ],
      }
    : null;

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Wallet Section */}
      <div className="flex flex-col items-center gap-4 p-6 border border-gray-200 rounded-xl shadow-sm bg-white dark:bg-zinc-800 dark:border-zinc-700">
        <h2 className="text-xl font-bold">Your Wallet</h2>
        <WalletMultiButton />
        {publicKey && (
          <div className="text-center mt-2">
            <p className="text-sm text-gray-500 dark:text-gray-400">Current Balance</p>
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">
              {balance !== null ? balance.toFixed(4) : "..."} SOL
            </p>
          </div>
        )}
      </div>

      {/* Dashboard Forecast Section */}
      <div className="border border-gray-200 rounded-xl shadow-sm bg-white dark:bg-zinc-800 dark:border-zinc-700 p-6">
        <h2 className="text-xl font-bold mb-6">Market & Forecast Dashboard</h2>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-2 rounded mb-4">
            Error: {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-8">
            <p className="text-gray-500">Loading forecast data...</p>
          </div>
        ) : forecast ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Stock Chart */}
            {stockChartData && (
              <div className="p-4 border border-gray-200 rounded-lg dark:border-zinc-700">
                <h3 className="text-lg font-semibold mb-4">Stock Forecast (AAPL)</h3>
                <Line
                  data={stockChartData}
                  options={{
                    responsive: true,
                    plugins: {
                      legend: { position: "top" },
                      title: { display: false },
                    },
                    scales: {
                      y: { beginAtZero: false },
                    },
                  }}
                />
                <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded">
                  <p className="text-sm font-medium">
                    Prediction: {forecast.stocks.predicted[forecast.stocks.predicted.length - 1]?.toFixed(2)}
                  </p>
                </div>
              </div>
            )}

            {/* Crypto Chart */}
            {cryptoChartData && (
              <div className="p-4 border border-gray-200 rounded-lg dark:border-zinc-700">
                <h3 className="text-lg font-semibold mb-4">Crypto Forecast (BTC)</h3>
                <Line
                  data={cryptoChartData}
                  options={{
                    responsive: true,
                    plugins: {
                      legend: { position: "top" },
                      title: { display: false },
                    },
                    scales: {
                      y: { beginAtZero: false },
                    },
                  }}
                />
                <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded">
                  <p className="text-sm font-medium">
                    Prediction: {forecast.crypto.predicted[forecast.crypto.predicted.length - 1]?.toFixed(2)}
                  </p>
                </div>
              </div>
            )}

            {/* Sentiment Chart */}
            {sentimentChartData && (
              <div className="p-4 border border-gray-200 rounded-lg dark:border-zinc-700">
                <h3 className="text-lg font-semibold mb-4">Market Sentiment</h3>
                <Bar
                  data={sentimentChartData}
                  options={{
                    responsive: true,
                    indexAxis: "y",
                    plugins: {
                      legend: { display: false },
                      title: { display: false },
                    },
                    scales: {
                      x: { max: 100, min: 0 },
                    },
                  }}
                />
                <div className="mt-4 p-3 bg-purple-50 dark:bg-purple-900/20 rounded">
                  <p className="text-sm font-medium">
                    Score: {forecast.sentiment.values[0]?.toFixed(1)}/100
                  </p>
                </div>
              </div>
            )}

            {/* Cloud Metrics */}
            {forecast.cloud.labels && forecast.cloud.labels.length > 0 && (
              <div className="p-4 border border-gray-200 rounded-lg dark:border-zinc-700">
                <h3 className="text-lg font-semibold mb-4">Cloud Metrics</h3>
                <Line
                  data={{
                    labels: forecast.cloud.labels,
                    datasets: [
                      {
                        label: "CPU Usage (%)",
                        data: forecast.cloud.values,
                        borderColor: "rgb(139, 92, 246)",
                        backgroundColor: "rgba(139, 92, 246, 0.1)",
                        tension: 0.4,
                        fill: true,
                      },
                    ],
                  }}
                  options={{
                    responsive: true,
                    plugins: {
                      legend: { position: "top" },
                      title: { display: false },
                    },
                    scales: {
                      y: { beginAtZero: true, max: 100 },
                    },
                  }}
                />
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
};