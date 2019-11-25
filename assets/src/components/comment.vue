<template>
  <user-panel :pic="pic">
    <template slot="heading">
      <strong>{{ name }}</strong>
      <span class="text-muted" :title="displayCreated">
        {{ displayCreated }}
      </span>
    </template>

    <template>
      <para :text="body"></para>
    </template>
  </user-panel>
</template>

<script>
  import userPanel from './userPanel.vue'
  import para from './para.vue'
  import moment from 'moment'

export default {
    props: ['pic', 'name', 'created', 'body'],
    components: {
      userPanel,
      para
    },
    computed: {
      displayCreated: function() {
        return moment(this.created).format('Do MMM YYYY, hh:mm A')
      }
    }
  }
</script>

