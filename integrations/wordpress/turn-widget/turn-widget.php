<?php
/** Plugin Name: TurnWidget */
function turn_widget_shortcode($atts) {
  $atts = shortcode_atts(array('id' => ''), $atts, 'turn_widget');
  $id = esc_attr($atts['id']);
  if (!$id) return '';
  wp_enqueue_script('turn-widget', 'https://WIDGET_APP_DOMAIN/embed/v1/widget.js', array(), '1.0.0', false);
  return '<turn-widget widget-id="' . $id . '"></turn-widget>';
}
add_shortcode('turn_widget', 'turn_widget_shortcode');
