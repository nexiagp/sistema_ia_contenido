<?php
/**
 * Plugin Name: Nexia GP Rank Math REST Bridge
 * Description: Allows authenticated post editors to sync three Rank Math SEO fields through the WordPress REST API.
 * Version: 1.0.0
 * Author: Nexia GP
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

add_action( 'init', static function () {
    foreach ( array( 'rank_math_title', 'rank_math_description', 'rank_math_focus_keyword' ) as $meta_key ) {
        register_post_meta( 'post', $meta_key, array(
            'type'              => 'string',
            'single'            => true,
            'show_in_rest'      => true,
            'sanitize_callback' => 'sanitize_text_field',
            'auth_callback'     => static function ( $allowed, $key, $object_id ) {
                return $object_id && current_user_can( 'edit_post', $object_id );
            },
        ) );
    }
} );
