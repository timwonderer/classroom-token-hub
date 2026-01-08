# Classroom Token Hub - v1.6.0 Roadmap and Half-Built Features

**Document Date**: January 1, 2026  
**Current Version**: 1.6.0  
**Target Version**: 1.7.0

---

## Executive Summary

Following comprehensive audit of the repository for v1.6.0 release, this document outlines:
1. Half-built features that need completion
2. Logical next steps for v1.7.0 and beyond
3. Recommendations for feature prioritization

---

## Half-Built Features Identified

### 1. Collective Goals (Store Items)

**Status**: 60% complete - Backend and API implemented, teacher UI needs work

**What Exists**:
- Database columns: `StoreItem.collective_goal_type` and `collective_goal_target`
- Migration: `o2p3q4r5s6t7_add_collective_goal_settings.py` (November 2025)
- Form validation: `StoreItemForm` includes collective goal fields with proper validators
- API logic: `/api/store/purchase` handles collective purchases with threshold checking
- Student UI: `student_shop.html` displays collective goal progress and types

**What's Missing**:
- [ ] Teacher UI for creating collective goal items in store management interface
- [ ] Visual progress indicators on teacher store management dashboard
- [ ] Notification system when collective goals are met/achieved
- [ ] Complete redemption workflow for collective items
- [ ] Teacher analytics showing which collective goals are popular
- [ ] Documentation in teacher manual about collective goals
- [ ] Documentation in student guide about how collective goals work

**Functionality**:
- **Fixed Type**: Requires specific number of purchases (e.g., "10 students must purchase")
- **Whole Class Type**: Requires all enrolled students to purchase

**Use Cases**:
- Class Pizza Party requiring all students to contribute
- Outdoor Learning Day requiring 20 student purchases
- Team building exercises tied to collective financial participation

**Priority**: Medium-High (functional but incomplete)
**Estimated Effort**: 2-3 weeks
**Recommendation**: Complete for v1.7.0 - This feature is already functional on the backend and student side, just needs teacher interface polish

---

### 2. Jobs Feature

**Status**: Removed but preserved in git history - Awaiting reimplementation

**Git History**:
- Started: commit `0800640` (models)
- Expanded: commits `c9378b7` (forms), `e2de8bd` (routes, 514 lines)
- Tested: commit `8a1b0bd` (comprehensive tests)
- Removed: commit `a04b574` (December 2025, kept merge migration only)

**What Existed Before Removal**:
- 5 database models: `JobTemplate`, `Job`, `JobApplication`, `JobEmployee`, `JobContract`
- Complete admin routes file: `app/routes/admin_jobs.py` (514 lines)
- Flask forms for all job operations
- Payment processing integration with transactions
- Application and approval system
- Termination system with warnings and penalties
- Comprehensive test coverage

**Two Job Types Designed**:

1. **Employee Jobs**: Long-term positions with regular pay
   - Application and approval process
   - Regular salary payments (daily/weekly/monthly)
   - Multiple vacancy slots per job
   - Termination system with consequences

2. **Contract Jobs**: One-off bounties, first-come-first-served
   - No application required
   - Single payment upon completion
   - Quick turnaround for short-term tasks

**Use Cases**:
- Classroom Helper earning weekly salary
- Technology Assistant managing devices
- Project bounties for one-time tasks
- Teaching work ethic and job responsibility

**Priority**: Medium (valuable educational feature)
**Estimated Effort**: 6-8 weeks (restoration + modernization + multi-tenancy updates)
**Recommendation**: Defer to v1.8+ - Restore and modernize when resources allow

---

## Completed Features (Recently)

### v1.6.0
- Repository organization and file consolidation
- Multi-tenancy fixes (HallPassSettings)
- Passkey authentication reliability improvements

### v1.5.0
- Issue reporting and resolution system
- Attendance issue reporting
- Security hardening and attack surface audit

### v1.4.0
- Announcement system (teacher and system admin)
- UI/UX redesign with personalized greetings
- Accordion navigation
- Student dashboard improvements

### v1.3.0
- Passwordless authentication (WebAuthn/FIDO2)
- Encrypted TOTP secrets
- Service worker improvements

---

## Roadmap for v1.7.0

### Priority 1: Complete Collective Goals
**Effort**: 2-3 weeks

**Tasks**:
1. Add collective goal UI to store item creation/edit forms
2. Show collective goal progress on teacher store dashboard
3. Implement notification system for goal completion
4. Add teacher analytics for collective goal performance
5. Document feature in teacher and student guides
6. Add tests for teacher UI interactions

**Rationale**: Feature is 60% complete and functional, just needs polish. Quick win with high value.

### Priority 2: Analytics and Reporting Enhancements
**Effort**: 3-4 weeks

**Tasks**:
1. Enhanced transaction reporting and filtering
2. Class-wide financial health dashboard
3. Student progress reports (downloadable)
4. Attendance analytics improvements
5. Insurance and rent compliance reports

**Rationale**: Teachers need better visibility into class economy performance.

### Priority 3: Mobile Experience Polish
**Effort**: 2-3 weeks

**Tasks**:
1. Optimize PWA performance
2. Improve offline functionality
3. Enhance touch interfaces
4. Better mobile navigation patterns
5. Test on more devices

**Rationale**: Continue improving mobile-first experience from v1.2.0.

### Priority 4: Performance Optimizations
**Effort**: 2-3 weeks

**Tasks**:
1. Database query optimization
2. Caching improvements
3. Static asset optimization
4. Reduce page load times
5. Profile and optimize slow endpoints

**Rationale**: As usage grows, performance becomes more critical.

---

## Roadmap for v1.8.0+

### Jobs Feature Restoration
**Effort**: 6-8 weeks

**Approach**:
1. Restore models from git history
2. Update for current multi-tenancy patterns (join_code scoping)
3. Modernize forms and routes
4. Rebuild test coverage
5. Create student job board interface
6. Add teacher analytics
7. Document thoroughly

**Benefits**:
- Diverse earning opportunities for students
- Teaching work ethic and responsibility
- More engaging classroom economy

### Custom Condition Builder
**Effort**: 12-18 weeks

**Phases**:
1. JSON-based rules engine (4-6 weeks)
2. Simple form builder UI (2-3 weeks)
3. Drag-and-drop enhancement (2-3 weeks)
4. Full visual programming with Blockly (4-6 weeks)

**Benefits**:
- Power users can create complex rules
- Custom triggers across all economy features
- Greater flexibility without code changes

---

## Technical Debt

### Low Priority Cleanup
1. Remove unused imports identified in codebase
2. Consolidate similar template patterns
3. Improve code documentation
4. Refactor large route files into smaller modules

### Testing Coverage
1. Add more integration tests
2. Improve test performance
3. Add visual regression tests
4. Automated accessibility testing

---

## Feature Prioritization Matrix

### High Impact, Low Effort (Do First)
- Complete collective goals feature
- Mobile experience polish
- Performance optimizations

### High Impact, High Effort (Plan Carefully)
- Jobs feature restoration
- Advanced analytics and reporting
- Custom condition builder

### Low Impact, Low Effort (Nice to Have)
- UI tweaks and polish
- Additional store item types
- More notification options

### Low Impact, High Effort (Defer)
- Full internationalization
- Parent portal
- Curriculum integration tools

---

## Recommendations

### Immediate (v1.7.0 - Q1 2026)
1. Complete collective goals feature (2-3 weeks)
2. Enhanced analytics and reporting (3-4 weeks)
3. Mobile experience polish (2-3 weeks)
4. Performance optimizations (2-3 weeks)

**Total**: 10-14 weeks of development work

### Medium Term (v1.8.0 - Q2 2026)
1. Jobs feature restoration and modernization (6-8 weeks)
2. Advanced teacher analytics (3-4 weeks)
3. Student engagement features (3-4 weeks)

### Long Term (v2.0+ - Q3 2026 and beyond)
1. Custom condition builder (12-18 weeks)
2. Internationalization (6-8 weeks)
3. Parent portal (8-10 weeks)

---

## Success Metrics

### For v1.7.0
- [ ] Collective goals feature 100% complete and documented
- [ ] Teacher analytics dashboard launched
- [ ] Page load times reduced by 30%
- [ ] Mobile PWA install rate increased by 20%
- [ ] Zero critical bugs reported

### For v1.8.0
- [ ] Jobs feature fully functional and tested
- [ ] Student engagement metrics improved
- [ ] Teacher satisfaction score > 4.5/5
- [ ] Platform performance under load verified

---

## Conclusion

The v1.6.0 audit revealed a well-organized, feature-rich platform with clear paths forward. The collective goals feature is the obvious quick win for v1.7.0, being 60% complete and highly valuable. The jobs feature, while currently removed, represents a significant educational opportunity for future releases when resources permit.

Focus for next releases should be on:
1. Completing half-built features (collective goals)
2. Enhancing existing features (analytics, mobile experience)
3. Optimizing performance and stability
4. Planning larger features (jobs, custom conditions) for future releases

---

**Last Updated**: January 1, 2026  
**Author**: Repository Audit Team  
**Next Review**: March 1, 2026 (for v1.7.0 planning)
