from django.urls import path

from . import admin_views as adm
from . import customer as cus
from . import exec_views as ex
from . import seller as sel

app_name = 'portals'

urlpatterns = [
    # ---- customer
    path('account/', cus.home, name='customer_home'),
    path('account/orders/', cus.orders, name='customer_orders'),
    path('account/orders/<str:number>/', cus.order_detail, name='order_detail'),
    path('account/orders/cancel/<int:so_id>/', cus.order_cancel, name='order_cancel'),
    path('account/wishlist/', cus.wishlist, name='customer_wishlist'),
    path('account/addresses/', cus.addresses, name='customer_addresses'),
    path('account/addresses/<int:pk>/delete/', cus.address_delete, name='address_delete'),
    path('account/profile/', cus.profile, name='profile'),

    # ---- seller
    path('seller/', sel.home, name='seller_home'),
    path('seller/orders/', sel.orders, name='seller_orders'),
    path('seller/orders/<int:pk>/', sel.order_detail, name='seller_order_detail'),
    path('seller/orders/<int:pk>/cancel/', sel.order_cancel, name='seller_order_cancel'),
    path('seller/products/', sel.products, name='seller_products'),
    path('seller/products/new/', sel.product_new, name='seller_product_new'),
    path('seller/products/<int:pk>/edit/', sel.product_edit, name='seller_product_edit'),
    path('seller/products/<int:pk>/toggle/', sel.product_toggle, name='seller_product_toggle'),
    path('seller/products/image/<int:pk>/delete/', sel.product_delete_image, name='seller_image_delete'),
    path('seller/reviews/', sel.reviews, name='seller_reviews'),
    path('seller/reviews/<int:pk>/reply/', sel.review_reply, name='seller_review_reply'),
    path('seller/analytics/', sel.analytics_view, name='seller_analytics'),
    path('seller/analytics/refresh/', sel.analytics_refresh, name='seller_analytics_refresh'),
    path('seller/payouts/', sel.payouts, name='seller_payouts'),
    path('seller/team/', sel.staff, name='seller_staff'),
    path('seller/team/new/', sel.staff_new, name='seller_staff_new'),
    path('seller/team/<int:pk>/toggle/', sel.staff_toggle, name='seller_staff_toggle'),
    path('seller/attendance/', sel.attendance, name='seller_attendance'),
    path('seller/profile/', sel.shop_profile, name='seller_profile'),

    # ---- administrator
    path('staff/admin/', adm.home, name='admin_home'),
    path('staff/admin/orders/', adm.orders, name='admin_orders'),
    path('staff/admin/orders/<str:number>/', adm.order_detail, name='admin_order_detail'),
    path('staff/admin/shop-orders/<int:pk>/', adm.shop_order, name='admin_shop_order'),
    path('staff/admin/shops/', adm.shops, name='admin_shops'),
    path('staff/admin/shops/<int:pk>/', adm.shop_edit, name='admin_shop_edit'),
    path('staff/admin/users/', adm.users, name='admin_users'),
    path('staff/admin/users/<int:pk>/', adm.user_edit, name='admin_user_edit'),
    path('staff/admin/users/<int:pk>/reset/', adm.user_reset, name='admin_user_reset'),
    path('staff/admin/staff/', adm.staff, name='admin_staff'),
    path('staff/admin/staff/new/', adm.staff_new, name='admin_staff_new'),
    path('staff/admin/categories/', adm.categories, name='admin_categories'),
    path('staff/admin/categories/new/', adm.category_edit, name='admin_category_new'),
    path('staff/admin/categories/<int:pk>/', adm.category_edit, name='admin_category_edit'),
    path('staff/admin/coupons/', adm.coupons, name='admin_coupons'),
    path('staff/admin/coupons/new/', adm.coupon_edit, name='admin_coupon_new'),
    path('staff/admin/coupons/<int:pk>/', adm.coupon_edit, name='admin_coupon_edit'),
    path('staff/admin/slides/', adm.slides, name='admin_slides'),
    path('staff/admin/slides/new/', adm.slide_edit, name='admin_slide_new'),
    path('staff/admin/slides/<int:pk>/', adm.slide_edit, name='admin_slide_edit'),
    path('staff/admin/payouts/', adm.payouts, name='admin_payouts'),
    path('staff/admin/payouts/<int:pk>/', adm.payout_action, name='admin_payout_action'),
    path('staff/admin/payments/', adm.payments, name='admin_payments'),
    path('staff/admin/attendance/', adm.attendance, name='admin_attendance'),
    path('staff/admin/audit/', adm.audit, name='admin_audit'),

    # ---- analyst
    path('staff/analyst/', ex.analyst_home, name='analyst_home'),
    path('staff/analyst/customers/', ex.analyst_customers, name='analyst_customers'),
    path('staff/analyst/products/', ex.analyst_products, name='analyst_products'),
    path('staff/analyst/forecast/', ex.analyst_forecast, name='analyst_forecast'),
    path('staff/analyst/refresh/', ex.analyst_refresh, name='analyst_refresh'),
    path('staff/analyst/export/<str:kind>/', ex.analyst_export, name='analyst_export'),

    # ---- CEO
    path('staff/ceo/', ex.ceo_home, name='ceo_home'),
    path('staff/ceo/shops/', ex.ceo_shops, name='ceo_shops'),

    # ---- developer
    path('staff/developer/', ex.developer_home, name='developer_home'),
    path('staff/developer/audit/', ex.developer_audit, name='developer_audit'),
    path('staff/developer/webhooks/', ex.developer_webhooks, name='developer_webhooks'),
    path('staff/developer/api/', ex.developer_api, name='developer_api'),
    path('staff/developer/api/token/', ex.developer_token, name='developer_token'),
    path('staff/developer/jobs/', ex.developer_jobs, name='developer_jobs'),

    # ---- support
    path('staff/support/', ex.support_home, name='support_home'),
    path('staff/support/orders/<str:number>/', ex.support_order, name='support_order'),
]
