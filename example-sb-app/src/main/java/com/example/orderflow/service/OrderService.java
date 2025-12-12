package com.example.orderflow.service;

import com.example.orderflow.model.Order;
import com.example.orderflow.model.OrderItem;
import com.example.orderflow.model.OrderStatus;
import com.example.orderflow.repository.OrderRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

@Service
@Transactional
public class OrderService {

    private static final Logger log = LoggerFactory.getLogger(OrderService.class);

    private final OrderRepository orderRepository;
    private final NotificationService notificationService;

    @Value("${orderflow.orders.default-region:US}")
    private String defaultRegion;

    @Value("${orderflow.orders.max-items-per-order:100}")
    private int maxItemsPerOrder;

    @Value("${orderflow.features.auto-confirm:false}")
    private boolean autoConfirm;

    public OrderService(OrderRepository orderRepository, NotificationService notificationService) {
        this.orderRepository = orderRepository;
        this.notificationService = notificationService;
    }

    public Order createOrder(Order order) {
        log.info("Creating new order for customer: {}", order.getCustomerId());

        if (order.getItems().size() > maxItemsPerOrder) {
            throw new IllegalArgumentException(
                    "Order cannot have more than " + maxItemsPerOrder + " items");
        }

        if (order.getRegion() == null) {
            order.setRegion(defaultRegion);
        }

        Order savedOrder = orderRepository.save(order);
        log.debug("Order {} created with status {}", savedOrder.getId(), savedOrder.getStatus());

        if (autoConfirm) {
            log.info("Auto-confirming order {}", savedOrder.getId());
            savedOrder.setStatus(OrderStatus.CONFIRMED);
            savedOrder = orderRepository.save(savedOrder);
            notificationService.sendOrderConfirmation(savedOrder);
        }

        return savedOrder;
    }

    @Cacheable(value = "orders", key = "#id")
    @Transactional(readOnly = true)
    public Optional<Order> getOrder(Long id) {
        log.debug("Fetching order {}", id);
        return orderRepository.findById(id);
    }

    @Transactional(readOnly = true)
    public Order getOrderWithItems(Long id) {
        log.debug("Fetching order {} with items", id);
        return orderRepository.findByIdWithItems(id);
    }

    @Transactional(readOnly = true)
    public List<Order> getOrdersByCustomer(String customerId) {
        log.debug("Fetching orders for customer {}", customerId);
        return orderRepository.findByCustomerId(customerId);
    }

    @Transactional(readOnly = true)
    public List<Order> getOrdersByStatus(OrderStatus status) {
        log.debug("Fetching orders with status {}", status);
        return orderRepository.findByStatus(status);
    }

    @Transactional(readOnly = true)
    public List<Order> getOrdersByRegion(String region) {
        log.debug("Fetching orders in region {}", region);
        return orderRepository.findByRegion(region);
    }

    @Transactional(readOnly = true)
    public List<Order> getAllOrders() {
        log.debug("Fetching all orders");
        return orderRepository.findAll();
    }

    @CacheEvict(value = "orders", key = "#id")
    public Order updateOrderStatus(Long id, OrderStatus newStatus) {
        log.info("Updating order {} status to {}", id, newStatus);

        Order order = orderRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Order not found: " + id));

        OrderStatus oldStatus = order.getStatus();
        order.setStatus(newStatus);
        Order updatedOrder = orderRepository.save(order);

        notificationService.sendStatusUpdate(updatedOrder, oldStatus, newStatus);

        return updatedOrder;
    }

    @CacheEvict(value = "orders", key = "#id")
    public Order addItemToOrder(Long id, OrderItem item) {
        log.info("Adding item {} to order {}", item.getProductId(), id);

        Order order = orderRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Order not found: " + id));

        if (order.getItems().size() >= maxItemsPerOrder) {
            throw new IllegalArgumentException(
                    "Order cannot have more than " + maxItemsPerOrder + " items");
        }

        order.addItem(item);
        return orderRepository.save(order);
    }

    @CacheEvict(value = "orders", key = "#id")
    public void cancelOrder(Long id) {
        log.info("Cancelling order {}", id);

        Order order = orderRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Order not found: " + id));

        if (order.getStatus() == OrderStatus.SHIPPED || order.getStatus() == OrderStatus.DELIVERED) {
            throw new IllegalStateException(
                    "Cannot cancel order in status: " + order.getStatus());
        }

        order.setStatus(OrderStatus.CANCELLED);
        orderRepository.save(order);
        notificationService.sendCancellationNotice(order);
    }

    @Transactional(readOnly = true)
    public long countOrdersByStatus(OrderStatus status) {
        return orderRepository.countByStatus(status);
    }
}
