<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div class="card">
      <div class="card-header">
        <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
      </div>
      <div class="budget-controls">
        <div class="budget-slider-row">
          <input
            type="range"
            min="0"
            max="10000"
            step="100"
            :value="budget"
            @input="budget = Number($event.target.value)"
            @change="loadRecommendations"
            class="budget-slider"
          />
          <span class="budget-value">{{ currencySymbol }}{{ budget.toLocaleString() }}</span>
        </div>
        <div class="category-select-row">
          <label for="restock-category">{{ t('restocking.categoryLabel') }}</label>
          <select id="restock-category" v-model="selectedCategory">
            <option value="all">{{ t('filters.all') }}</option>
            <option value="Circuit Boards">{{ t('categories.circuitBoards') }}</option>
            <option value="Sensors">{{ t('categories.sensors') }}</option>
            <option value="Actuators">{{ t('categories.actuators') }}</option>
            <option value="Controllers">{{ t('categories.controllers') }}</option>
            <option value="Power Supplies">{{ t('categories.powerSupplies') }}</option>
          </select>
        </div>
      </div>
    </div>

    <div v-if="successMessage" class="success-banner">
      <p>{{ successMessage }}</p>
      <p v-if="successDetails">{{ successDetails }}</p>
      <router-link to="/orders">{{ t('restocking.viewOrders') }}</router-link>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div v-if="recommendations.length > 0" class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.summary.totalCost') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ totalRecommendedCost.toLocaleString() }}</div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.summary.budget') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ budget.toLocaleString() }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.summary.remaining') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ remainingBudget.toLocaleString() }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendedItems') }}</h3>
          <button
            class="place-order-btn"
            :disabled="recommendations.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>
        <div v-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.noRecommendations') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.currentDemand') }}</th>
                <th>{{ t('restocking.table.forecastedDemand') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.recommendedQuantity') }}</th>
                <th>{{ t('restocking.table.recommendedCost') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recommendations" :key="item.item_sku">
                <td><strong>{{ item.item_sku }}</strong></td>
                <td>{{ item.item_name }}</td>
                <td>
                  <span :class="['badge', item.trend]">
                    {{ t(`trends.${item.trend}`) }}
                  </span>
                </td>
                <td>{{ item.current_demand }}</td>
                <td>{{ item.forecasted_demand }}</td>
                <td>{{ currencySymbol }}{{ item.unit_cost.toLocaleString() }}</td>
                <td>{{ item.recommended_quantity }}</td>
                <td><strong>{{ currencySymbol }}{{ item.recommended_cost.toLocaleString() }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency } = useI18n()
    const { selectedCategory } = useFilters()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    const budget = ref(2500)
    const loading = ref(false)
    const error = ref(null)
    const submitting = ref(false)
    const recommendations = ref([])
    const successMessage = ref(null)
    const successDetails = ref(null)

    const totalRecommendedCost = computed(() => {
      return recommendations.value.reduce((sum, item) => sum + item.recommended_cost, 0)
    })

    const remainingBudget = computed(() => {
      return budget.value - totalRecommendedCost.value
    })

    const loadRecommendations = async () => {
      successMessage.value = null
      successDetails.value = null
      loading.value = true
      error.value = null
      try {
        recommendations.value = await api.getRestockRecommendations(budget.value, selectedCategory.value)
      } catch (err) {
        error.value = 'Failed to load restock recommendations'
        console.error('Load error:', err)
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      submitting.value = true
      error.value = null
      try {
        const orderData = {
          items: recommendations.value.map(r => ({
            item_sku: r.item_sku,
            quantity: r.recommended_quantity
          })),
          budget: budget.value
        }
        const order = await api.submitRestockOrder(orderData)
        successMessage.value = t('restocking.orderSuccess', { orderNumber: order.order_number })
        successDetails.value = t('restocking.leadTime', { days: order.lead_time_days })
        recommendations.value = []
      } catch (err) {
        error.value = 'Failed to submit restock order'
        console.error('Submit error:', err)
      } finally {
        submitting.value = false
      }
    }

    watch(selectedCategory, () => {
      loadRecommendations()
    })

    onMounted(() => {
      loadRecommendations()
    })

    return {
      t,
      currencySymbol,
      budget,
      selectedCategory,
      loading,
      error,
      submitting,
      recommendations,
      successMessage,
      successDetails,
      totalRecommendedCost,
      remainingBudget,
      loadRecommendations,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-controls {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.budget-slider-row {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}

.budget-slider {
  flex: 1;
  accent-color: #2563eb;
}

.budget-value {
  min-width: 100px;
  text-align: right;
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
}

.category-select-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.category-select-row label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
}

.category-select-row select {
  padding: 0.5rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.875rem;
  color: #0f172a;
  background: white;
}

.place-order-btn {
  padding: 0.5rem 1.25rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background 0.2s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-size: 0.938rem;
}

.success-banner {
  background: #d1fae5;
  border: 1px solid #6ee7b7;
  color: #065f46;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.25rem;
  font-size: 0.938rem;
}

.success-banner p {
  margin: 0 0 0.375rem 0;
}

.success-banner a {
  color: #065f46;
  font-weight: 600;
  text-decoration: underline;
}
</style>
