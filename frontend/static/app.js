// Example forecast data (replace with API response)
const labels = ["Hour 1", "Hour 2", "Hour 3", "Hour 4", "Hour 5"];
const actualPrices = [145, 147, 146, 148, 149];
const predictedPrices = [146, 148, 147, 149, 150];

const ctx = document.getElementById("forecastChart").getContext("2d");
const forecastChart = new Chart(ctx, {
  type: "line",
  data: {
    labels: labels,
    datasets: [
      {
        label: "Actual Prices",
        data: actualPrices,
        borderColor: "blue",
        fill: false,
      },
      {
        label: "Predicted Prices",
        data: predictedPrices,
        borderColor: "red",
        borderDash: [5, 5],
        fill: false,
      },
    ],
  },
  options: {
    responsive: true,
    plugins: {
      legend: {
        position: "top",
      },
      title: {
        display: true,
        text: "Stock Forecast (AAPL)"
      }
    }
  }
});

// Screen Reader Functions
function startReader() {
  const msg = new SpeechSynthesisUtterance("Forecast chart loaded. Prices are trending upward.");
  window.speechSynthesis.speak(msg);
}

function stopReader() {
  window.speechSynthesis.cancel();
}
