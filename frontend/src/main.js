import './main.css'
import { mountIslands } from './islands/index.js'

// Mount all Vue islands when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mountIslands)
} else {
  mountIslands()
}
