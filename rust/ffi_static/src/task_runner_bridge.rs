// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

use core::future::Future;
use core::task::{Context, Poll, Waker, RawWaker, RawWakerVTable};
use core::pin::Pin;

// Pointer to Chromium's base::SequencedTaskRunner
pub type TaskRunnerPtr = *mut core::ffi::c_void;

// Callback signature for task execution in C++: void(*)(void* user_data)
pub type ChromiumCallback = extern "C" fn(user_data: *mut core::ffi::c_void);

// Signature of C++ helper to post task:
// bool PostTask(TaskRunnerPtr runner, ChromiumCallback callback, void* user_data)
pub type PostTaskFn = unsafe extern "C" fn(runner: TaskRunnerPtr, callback: ChromiumCallback, user_data: *mut core::ffi::c_void) -> u32;

pub struct TaskSlot {
    future: Option<Pin<&'static mut (dyn Future<Output = ()> + Send)>>,
    task_runner: TaskRunnerPtr,
    post_task_fn: Option<PostTaskFn>,
}

static mut GLOBAL_TASK_SLOT: TaskSlot = TaskSlot {
    future: None,
    task_runner: core::ptr::null_mut(),
    post_task_fn: None,
};

unsafe fn waker_clone(data: *const ()) -> RawWaker {
    RawWaker::new(data, &WAKER_VTABLE)
}

unsafe fn waker_wake(data: *const ()) {
    unsafe {
        let slot = &mut *core::ptr::addr_of_mut!(GLOBAL_TASK_SLOT);
        if let Some(post_fn) = slot.post_task_fn {
            if !slot.task_runner.is_null() {
                post_fn(slot.task_runner, run_executor_callback, data as *mut _);
            }
        }
    }
}

unsafe fn waker_wake_by_ref(data: *const ()) {
    unsafe { waker_wake(data) }
}

unsafe fn waker_drop(_data: *const ()) {}

static WAKER_VTABLE: RawWakerVTable = RawWakerVTable::new(
    waker_clone,
    waker_wake,
    waker_wake_by_ref,
    waker_drop,
);

extern "C" fn run_executor_callback(user_data: *mut core::ffi::c_void) {
    unsafe {
        let slot = &mut *core::ptr::addr_of_mut!(GLOBAL_TASK_SLOT);
        if let Some(ref mut fut) = slot.future {
            let raw_waker = RawWaker::new(user_data as *const (), &WAKER_VTABLE);
            let waker = Waker::from_raw(raw_waker);
            let mut cx = Context::from_waker(&waker);
            
            match fut.as_mut().poll(&mut cx) {
                Poll::Ready(()) => {
                    slot.future = None;
                }
                Poll::Pending => {}
            }
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn chromium_rust_async_executor_init(
    runner: TaskRunnerPtr,
    post_fn: PostTaskFn,
) {
    unsafe {
        let slot = &mut *core::ptr::addr_of_mut!(GLOBAL_TASK_SLOT);
        slot.task_runner = runner;
        slot.post_task_fn = Some(post_fn);
    }
}

pub struct YieldFuture {
    count: usize,
}

impl YieldFuture {
    pub fn new(count: usize) -> Self {
        Self { count }
    }
}

impl Future for YieldFuture {
    type Output = ();

    fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
        if self.count == 0 {
            Poll::Ready(())
        } else {
            self.count -= 1;
            cx.waker().wake_by_ref();
            Poll::Pending
        }
    }
}

static mut TEST_YIELD_FUTURE: Option<YieldFuture> = None;

#[no_mangle]
pub unsafe extern "C" fn chromium_rust_async_executor_test_run(
    yield_count: usize,
) -> u32 {
    unsafe {
        let fut = YieldFuture::new(yield_count);
        let test_future = core::ptr::addr_of_mut!(TEST_YIELD_FUTURE);
        *test_future = Some(fut);
        
        let slot = &mut *core::ptr::addr_of_mut!(GLOBAL_TASK_SLOT);
        let future_ptr = match (*test_future).as_mut() {
            Some(future) => future as *mut YieldFuture,
            None => core::hint::unreachable_unchecked(),
        };
        let pin_fut: Pin<&'static mut YieldFuture> = Pin::new_unchecked(&mut *future_ptr);
        slot.future = Some(pin_fut);
        
        run_executor_callback(core::ptr::null_mut());
        
        if slot.future.is_none() {
            1 // Completed immediately
        } else {
            0 // Suspended and pending C++ scheduling
        }
    }
}
