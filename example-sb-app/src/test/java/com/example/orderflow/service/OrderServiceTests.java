package com.example.orderflow.service;

import com.example.orderflow.model.Order;
import com.example.orderflow.model.OrderItem;
import com.example.orderflow.model.OrderStatus;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@Transactional
class OrderServiceTests {

    @Autowired
    private OrderService orderService;

    @Test
    void shouldCreateOrder() {
        Order order = new Order();
        order.setCustomerId("CUST-001");
        order.addItem(new OrderItem("PROD-001", "Test Product", 2, new BigDecimal("29.99")));

        Order saved = orderService.createOrder(order);

        assertNotNull(saved.getId());
        assertEquals("CUST-001", saved.getCustomerId());
        assertEquals(OrderStatus.PENDING, saved.getStatus());
        assertEquals(1, saved.getItems().size());
        assertEquals(new BigDecimal("59.98"), saved.getTotalAmount());
    }

    @Test
    void shouldUpdateOrderStatus() {
        Order order = new Order();
        order.setCustomerId("CUST-002");
        order.addItem(new OrderItem("PROD-002", "Another Product", 1, new BigDecimal("49.99")));
        Order saved = orderService.createOrder(order);

        Order updated = orderService.updateOrderStatus(saved.getId(), OrderStatus.CONFIRMED);

        assertEquals(OrderStatus.CONFIRMED, updated.getStatus());
    }

    @Test
    void shouldCancelOrder() {
        Order order = new Order();
        order.setCustomerId("CUST-003");
        order.addItem(new OrderItem("PROD-003", "Product to Cancel", 1, new BigDecimal("19.99")));
        Order saved = orderService.createOrder(order);

        orderService.cancelOrder(saved.getId());

        Order cancelled = orderService.getOrder(saved.getId()).orElseThrow();
        assertEquals(OrderStatus.CANCELLED, cancelled.getStatus());
    }
}
