function ekiobaApp(initialProducts, chartLabels, chartValues) {
  return {
    products: Array.isArray(initialProducts) ? initialProducts : [],
    cart: [],
    wallet: "",
    chain: "ton",
    checkoutStatus: "",
    checkoutLoading: false,
    uiPrompt: "",
    uiType: "button",
    generatedUI: "Awaiting prompt...",
    loadingUI: false,

    init() {
      this.renderChart(chartLabels, chartValues);
      document.body.addEventListener("htmx:afterSwap", (event) => {
        if (event.target && event.target.id === "products-grid") {
          this.refreshProducts();
        }
      });
    },

    async refreshProducts() {
      try {
        const response = await fetch("/api/store/products", { cache: "no-store" });
        const payload = await response.json();
        this.products = Array.isArray(payload.products) ? payload.products : [];
      } catch (_error) {
        this.products = [];
      }
    },

    addToCart(id) {
      const product = this.products.find((item) => String(item.id) === String(id));
      if (!product) {
        return;
      }

      const existing = this.cart.find((item) => String(item.id) === String(id));
      if (existing) {
        existing.quantity += 1;
        return;
      }

      this.cart.push({
        id: product.id,
        name: product.name,
        price: Number(product.price) || 0,
        quantity: 1,
      });
    },

    changeQty(id, quantity) {
      if (quantity <= 0) {
        this.cart = this.cart.filter((item) => String(item.id) !== String(id));
        return;
      }

      this.cart = this.cart.map((item) =>
        String(item.id) === String(id) ? { ...item, quantity: quantity } : item,
      );
    },

    get totalAmount() {
      return this.cart.reduce((sum, item) => sum + Number(item.price) * Number(item.quantity), 0);
    },

    money(value) {
      const amount = Number(value) || 0;
      return `Idia ${amount.toLocaleString("en-NG", { maximumFractionDigits: 2 })}`;
    },

    async checkout() {
      if (!this.wallet.trim() || this.cart.length === 0) {
        this.checkoutStatus = "Enter a wallet address and add products first.";
        return;
      }

      this.checkoutLoading = true;
      this.checkoutStatus = "Verifying payment intent...";
      try {
        const response = await fetch(`/api/pay/${this.chain}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            wallet: this.wallet.trim(),
            amount: this.totalAmount,
            cart: this.cart,
            proof: {},
          }),
        });
        const payload = await response.json();
        if (!response.ok) {
          this.checkoutStatus = payload.error || "Payment verification failed.";
          return;
        }

        this.checkoutStatus = payload.message || "Payment request accepted.";
        this.cart = [];
      } catch (_error) {
        this.checkoutStatus = "Payment verifier is unavailable right now.";
      } finally {
        this.checkoutLoading = false;
      }
    },

    async generateComponent() {
      const description = this.uiPrompt.trim();
      if (!description) {
        this.generatedUI = "Type a component description first.";
        return;
      }

      this.loadingUI = true;
      this.generatedUI = "Generating component...";
      try {
        const response = await fetch("/api/ai/generate-ui", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ description: description, componentType: this.uiType }),
        });
        const payload = await response.json();
        this.generatedUI = JSON.stringify(payload.component || payload, null, 2);
      } catch (_error) {
        this.generatedUI = "AI service unavailable. Try again later.";
      } finally {
        this.loadingUI = false;
      }
    },

    renderChart(labels, values) {
      const canvas = document.getElementById("catalogChart");
      if (!canvas || typeof Chart === "undefined") {
        return;
      }

      const safeLabels = Array.isArray(labels) ? labels : [];
      const safeValues = Array.isArray(values) ? values : [];

      new Chart(canvas, {
        type: "doughnut",
        data: {
          labels: safeLabels,
          datasets: [
            {
              data: safeValues,
              backgroundColor: ["#dd5b2f", "#2f6f6e", "#3f5b96", "#c18f27", "#8a4f77", "#5f8d42"],
              borderWidth: 1,
              borderColor: "#ffffff",
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: "bottom",
            },
          },
        },
      });
    },
  };
}
