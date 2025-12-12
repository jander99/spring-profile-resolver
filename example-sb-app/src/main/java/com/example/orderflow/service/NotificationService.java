package com.example.orderflow.service;

import com.example.orderflow.model.Order;
import com.example.orderflow.model.OrderStatus;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class NotificationService {

    private static final Logger log = LoggerFactory.getLogger(NotificationService.class);

    @Value("${orderflow.notifications.enabled:false}")
    private boolean notificationsEnabled;

    @Value("${orderflow.notifications.email.from:noreply@orderflow.example}")
    private String emailFrom;

    @Value("${orderflow.notifications.provider:log}")
    private String notificationProvider;

    public void sendOrderConfirmation(Order order) {
        if (!notificationsEnabled) {
            log.debug("Notifications disabled, skipping order confirmation for order {}", order.getId());
            return;
        }

        log.info("[{}] Sending order confirmation for order {} to customer {}",
                notificationProvider.toUpperCase(), order.getId(), order.getCustomerId());

        // In a real app, this would integrate with email/SMS/push notification services
        // The provider would be different based on the active profile (local vs aws vs gcp)
    }

    public void sendStatusUpdate(Order order, OrderStatus oldStatus, OrderStatus newStatus) {
        if (!notificationsEnabled) {
            log.debug("Notifications disabled, skipping status update for order {}", order.getId());
            return;
        }

        log.info("[{}] Sending status update for order {}: {} -> {}",
                notificationProvider.toUpperCase(), order.getId(), oldStatus, newStatus);
    }

    public void sendCancellationNotice(Order order) {
        if (!notificationsEnabled) {
            log.debug("Notifications disabled, skipping cancellation notice for order {}", order.getId());
            return;
        }

        log.info("[{}] Sending cancellation notice for order {} to customer {}",
                notificationProvider.toUpperCase(), order.getId(), order.getCustomerId());
    }

    public void sendShippingNotification(Order order, String trackingNumber) {
        if (!notificationsEnabled) {
            log.debug("Notifications disabled, skipping shipping notification for order {}", order.getId());
            return;
        }

        log.info("[{}] Sending shipping notification for order {} with tracking {}",
                notificationProvider.toUpperCase(), order.getId(), trackingNumber);
    }
}
