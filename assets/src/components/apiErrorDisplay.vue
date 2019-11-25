<template>
  <div class="api-errors">
    <div v-for="(errlist, key) in errors" :key="key" class="alert alert-danger" role="alert">
      <strong>{{ key }}:</strong>
      <ul v-if="errlist.length > 1">
        <li v-for="err in errlist" :key="err">
          {{ err }}
        </li>
      </ul>
      <template v-else>
        {{ errlist[0] }}
      </template>
    </div>
  </div>
</template>

<script>
  // Displays all errors in one place
  import { capitalize } from 'src/lib/utils.js'
  export default {
    props: {
      'errors': 'Object'
    },
    methods: {
      capitalize: capitalize
    }
  }
</script>
